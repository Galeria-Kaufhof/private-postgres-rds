Feature: add slave to existing master

  @loadtest
  Scenario: add slave and switch over as fast as possible
    Given a fresh postgres cluster
    When I halt and wipe out the slave
    When application inserts 2 batches of test data
    Then reading from postgres service url should work
    Then I run optional CHECKPOINT for faster replication
    When I initialize postgres cluster to configure slave replica again
    When I halt and wipe out the master
    Then reading from postgres service url should fail
    When I initialize postgres cluster to promote slave
    Then service url should point to INITIAL_SLAVE
    Then reading from postgres service url should work
    Then last committed batch - 2 - should be visible

