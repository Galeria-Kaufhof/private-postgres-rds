Feature: inventory works reliable under any circumstances
  Scenario: Server not available via ssh
    Given a fresh postgres cluster
    Then inventory CONFIGURED_MASTER should consist of INITIAL_MASTER
    When I reboot the master
    Then cluster initialization should fail
    When I wait for master to finish reboot
    Then I initialize postgres cluster to check success
