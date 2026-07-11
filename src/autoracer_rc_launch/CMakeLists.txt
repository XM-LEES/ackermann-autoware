cmake_minimum_required(VERSION 3.8)
project(autoracer_rc_launch)

find_package(ament_cmake REQUIRED)

install(DIRECTORY launch rviz config
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
