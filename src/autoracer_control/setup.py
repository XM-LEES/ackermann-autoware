from setuptools import setup

package_name = "autoracer_control"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/control.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Autoracer Team",
    maintainer_email="autoracer@example.com",
    description="Candidate control algorithms for Ackermann Autoware platforms.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "pure_pursuit_controller = autoracer_control.pure_pursuit_controller:main",
        ],
    },
)
