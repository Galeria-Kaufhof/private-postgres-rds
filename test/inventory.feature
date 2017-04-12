Feature: inventory works reliable under any circumstances
  Scenario: Server not available via ssh
    Given a fresh postgres cluster
    Then inventory master should consist of INITIAL_MASTER
    When I reboot the master
    Then inventory slaves should fail
    Then inventory master should fail
    When I wait for master to finish reboot
    Then inventory master should consist of INITIAL_MASTER
    Then inventory slaves should consist of INITIAL_SLAVE, SERVER3, SERVER4

  Scenario: inventory for rolling upgrade
    Given a fresh postgres cluster
    When I halt and wipe out the SERVER3
    Then inventory master should consist of INITIAL_MASTER
    Then inventory slaves should consist of INITIAL_SLAVE, SERVER3, SERVER4
    When I use inventory extra params 'ENFORCE_SLAVE_UPSTREAM=_SERVER3_'
    Then inventory slaves should consist of SERVER3
    When I use inventory extra params 'ENFORCE_MASTER=_SERVER3_'
    Then inventory master should consist of SERVER3
    Then inventory deactivate should consist of INITIAL_MASTER, INITIAL_SLAVE, SERVER4
    Then inventory slaves should be empty
