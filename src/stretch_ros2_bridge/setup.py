import os
from glob import glob

from setuptools import find_packages, setup

package_name = "stretch_ros2_bridge"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (
            os.path.join("share", package_name, "launch"),
            glob(os.path.join("launch", "*launch.[pxy][yma]*")),
        ),
    ],
    install_requires=["setuptools", "stretch"],
    zip_safe=True,
    maintainer="hello-robot",
    maintainer_email="hello-robot@todo.todo",
    description="TODO: Package description",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "camera_pose_publisher = stretch_ros2_bridge.nodes.camera_pose_publisher:main",
            "rotate_images = scripts.rotate_images",
            "state_estimator = stretch_ros2_bridge.nodes.state_estimator:main",
            "goto_controller = stretch_ros2_bridge.nodes.goto_controller:main",
            "odom_tf_publisher = stretch_ros2_bridge.nodes.odom_tf_publisher:main",
            "server = stretch_ros2_bridge.remote.server:main",
        ],
    },
)