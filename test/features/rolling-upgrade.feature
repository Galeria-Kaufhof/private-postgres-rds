Feature: rolling upgrade from master-slave to new master-slave
  Scenario: run rolling upgrade
    Given a fresh postgres cluster
    When I halt and wipe out the SERVER3
    When I halt and wipe out the SERVER4
    Then service url should point to INITIAL_MASTER

    When application inserts 2 batches of test data
    # When I start continuous db inserts in background
    When I invoke migrate-to-master --target-master=SERVER3
    # When I stop continuous db inserts in background
    # Then the last confirmed insert should be visible
    Then service url should point to SERVER3
    When application inserts 1 batches of test data
    Then service url should point to SERVER3
    Then reading from postgres service url should work
    Then last committed batch - 3 - should be visible

    When I halt and wipe out the SERVER3
    When I initialize postgres cluster to promote slave
    Then service url should point to SERVER4
    Then inventory CONFIGURED_MASTER should consist of SERVER4
    Then inventory CONFIGURED_SLAVE should consist of SERVER3
    Then reading from postgres service url should work
    Then last committed batch - 3 - should be visible
    # Then also the last confirmed insert + 3 batches should be visible

  Scenario: manual, enforced switch-over
    Then inventory CONFIGURED_SLAVE should be empty
    Then inventory CONFIGURED_MASTER should consist of SERVER3
    Given a fresh postgres cluster
    When application inserts 3 batches of test data
    When I invoke migrate-to-master --target-master=SERVER3
    Then service url should point to SERVER3
    Then reading from postgres service url should work
    Then last committed batch - 3 - should be visible
    Then inventory CONFIGURED_MASTER should consist of SERVER3
    Then inventory CONFIGURED_SLAVE should be empty
    Then inventory DEACTIVATED should consist of INITIAL_MASTER, INITIAL_SLAVE, SERVER4

