from setuptools import setup

package_name = "autoracer_sensing"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Autoracer Team",
    maintainer_email="autoracer@example.com",
    description="Minimal sensing adapters for Autoracer Hooke.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "c32_pointcloud_adapter = autoracer_sensing.c32_pointcloud_adapter:main",
            "pointcloud_voxel_filter = autoracer_sensing.pointcloud_voxel_filter:main",
            "velocity_to_fixposition_speed = autoracer_sensing.velocity_to_fixposition_speed:main",
        ],
    },
)
