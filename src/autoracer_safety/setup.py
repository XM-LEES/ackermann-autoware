from setuptools import setup

package_name = "autoracer_safety"

setup(
    name=package_name,
    version="0.1.0",
    packages=[package_name],
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/safety.launch.py"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="Autoracer Team",
    maintainer_email="autoracer@example.com",
    description="Platform-independent final safety gate before chassis adapters.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "command_gate = autoracer_safety.command_gate:main",
        ],
    },
)
