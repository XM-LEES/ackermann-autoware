cmake_minimum_required(VERSION 3.8)
project(autoracer_rc_bringup)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch rviz DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/start_rc_race.sh DESTINATION lib/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  find_package(ament_lint_auto REQUIRED)
  ament_add_pytest_test(rc_launch_contract test/test_rc_launch_contract.py)
  ament_add_pytest_test(rc_parameter_contract test/test_rc_parameter_contract.py)
  ament_add_pytest_test(rc_quickstart_contract test/test_rc_quickstart_contract.py)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
