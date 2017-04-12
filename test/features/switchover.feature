Feature: half automated pg master switch-over
  @loadtest
  Scenario: Postgres master switch-over
    Given a fresh postgres cluster
    Then service url should point to INITIAL_MASTER
    When application inserts 2 batches of test data
    Then reading from postgres service url should work
    Then last committed batch - 2 - should be visible
    # When I start continuous db inserts in background
    When I halt and wipe out the master
    Then reading from postgres service url should fail
    When I initialize postgres cluster to promote slave
    Then service url should point to INITIAL_SLAVE
    Then reading from postgres service url should work
    # When I stop continuous db inserts in background
    # Then the last confirmed insert should be visible
    Then last committed batch - 2 - should be visible

