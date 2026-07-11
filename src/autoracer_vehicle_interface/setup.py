from setuptools import setup

package_name = "autoracer_vehicle_interface"

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
    description="RC car serial vehicle interface for Autoracer.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "rc_serial_interface = autoracer_vehicle_interface.rc_serial_interface:main",
            "vehicle_velocity_converter = autoracer_vehicle_interface.vehicle_velocity_converter:main",
        ],
    },
)
