#!/usr/bin/env python

import math
import os
import sys
import time
from tempfile import NamedTemporaryFile

import matplotlib.pyplot as plt
import numpy as np
import orbslam3
import rclpy
import yaml
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseWithCovarianceStamped, TransformStamped
from rclpy.node import Node
from scipy.spatial.transform import Rotation as R
from sensor_msgs.msg import CameraInfo, Image, Imu
from tf2_ros import TransformBroadcaster
from tf_transformations import quaternion_from_euler

from stretch.navigation.utils.geometry import transformation_matrix_to_pose


class OrbSlam3(Node):
    def __init__(self):
        super().__init__("stretch_orbslam3")

        DIRNAME = get_package_share_directory("stretch_ros2_bridge")
        CONFIG_FILE = os.path.join(DIRNAME, "config", "orbslam_d435i.yaml")
        self.VOCABULARY_FILE = os.path.join(DIRNAME, "config", "ORBvoc.txt")

        # Load YAML configuration
        self.config = None
        with open(CONFIG_FILE, "r") as file:
            self.config = yaml.safe_load(file)

        # Check if ORBvocab.txt exists
        if not os.path.exists(self.VOCABULARY_FILE):
            # Check if ORBvoc.txt.tar.gz exists
            VOCABULARY_TAR_FILE = os.path.join(DIRNAME, "config", "ORBvoc.txt.tar.gz")

            if not os.path.exists(VOCABULARY_TAR_FILE):
                self.get_logger().error(f"ORB vocabulary file {self.VOCABULARY_FILE} not found")
                sys.exit(1)

            self.get_logger().info(f"Extracting {VOCABULARY_TAR_FILE} to {self.VOCABULARY_FILE}")
            os.system(f"tar -xvf {VOCABULARY_TAR_FILE} -C {DIRNAME}/config")

        self.slam = None

        self.tf_broadcaster = TransformBroadcaster(self)

        self.rgb_image = None
        self.depth_image = None
        self.accel_data = None
        self.gyro_data = None
        self.timestamp = None

        self.image_sub = self.create_subscription(
            Image, "/camera/color/image_raw", self.rgb_callback, 1
        )
        self.depth_sub = self.create_subscription(
            Image, "/camera/aligned_depth_to_color/image_raw", self.depth_callback, 1
        )
        self.accel_sub = self.create_subscription(
            Imu,
            "/camera/accel/sample",
            qos_profile=rclpy.qos.qos_profile_sensor_data,
            callback=self.accel_callback,
        )
        self.gyro_sub = self.create_subscription(
            Imu,
            "/camera/gyro/sample",
            qos_profile=rclpy.qos.qos_profile_sensor_data,
            callback=self.gyro_callback,
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo, "/camera/color/camera_info", self.camera_info_callback, 1
        )

    def camera_info_callback(self, msg):
        if self.slam is None:
            fx = msg.k[0]
            fy = msg.k[4]
            cx = msg.k[2]
            cy = msg.k[5]

            self.get_logger().info(f"Camera intrinsics: fx={fx}, fy={fy}, cx={cx}, cy={cy}")

            # Modify camera intrinsics in config
            self.config["Camera1.fx"] = float(fx)
            self.config["Camera1.fy"] = float(fy)
            self.config["Camera1.cx"] = float(cx)
            self.config["Camera1.cy"] = float(cy)

            height = int(msg.height)
            width = int(msg.width)

            # Modify image resolution in config
            self.config["Camera.height"] = height
            self.config["Camera.width"] = width

            self.config["Camera.type"] = "PinHole"

            # Save to a NamedTemporaryFile
            file = NamedTemporaryFile(mode="w", delete=False)
            yaml.dump(self.config, file)

            # Add %YAML:1.0 to the beginning of the file
            content = None
            with open(file.name, "r") as f:
                content = f.read()
            with open(file.name, "w") as f:
                f.write("%YAML:1.0\n" + content)

            file.close()

            self.get_logger().info(
                f"Using {self.VOCABULARY_FILE} and {file.name} for ORB-SLAM3 initialization"
            )

            self.slam = orbslam3.System(self.VOCABULARY_FILE, file.name, orbslam3.Sensor.RGBD)
            self.slam.set_use_viewer(True)
            self.slam.initialize()
            print("ORB-SLAM3 initialized")

    def rgb_callback(self, msg):
        self.rgb_image = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)

    def depth_callback(self, msg):
        self.depth_image = np.frombuffer(msg.data, dtype=np.uint16).reshape(msg.height, msg.width)
        self.timestamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9

    def accel_callback(self, msg):
        self.accel_data = msg

    def gyro_callback(self, msg):
        self.gyro_data = msg

    def run(self):
        while True:
            if (
                self.slam is None
                or self.rgb_image is None
                or self.depth_image is None
                or self.accel_data is None
                or self.gyro_data is None
            ):
                rclpy.spin_once(self, timeout_sec=0.1)
                continue

            accel = self.accel_data.linear_acceleration
            gyro = self.gyro_data.angular_velocity

            Tcw = self.slam.process_image_rgbd(
                self.rgb_image,
                self.depth_image,
                [accel.x, accel.y, accel.z, gyro.x, gyro.y, gyro.z],
                self.timestamp,
            )

            Tcw = np.array(Tcw).reshape(4, 4)
            Twc = np.linalg.inv(Tcw)
            pose = transformation_matrix_to_pose(Twc)
            self.publish_tf(pose)
            rclpy.spin_once(self, timeout_sec=0.1)

    def publish_tf(self, pose):
        x = pose.get_x()
        y = pose.get_y()
        z = pose.get_z()

        roll = pose.get_roll()
        pitch = pose.get_pitch()
        yaw = pose.get_yaw()
        q = quaternion_from_euler(yaw, pitch, -roll)

        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = "map"
        transform.child_frame_id = "base_link"
        transform.transform.translation.x = z
        transform.transform.translation.y = y
        transform.transform.translation.z = 0.0
        transform.transform.rotation.x = q[0]
        transform.transform.rotation.y = q[1]
        transform.transform.rotation.z = q[2]
        transform.transform.rotation.w = q[3]
        self.tf_broadcaster.sendTransform(transform)


def main(args=None):
    rclpy.init(args=args)

    node = OrbSlam3()
    node.run()

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()