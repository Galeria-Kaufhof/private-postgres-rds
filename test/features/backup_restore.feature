Feature: backup and restore work
  Scenario: Simple backup restore
    Given empty backup bucket
    Given a fresh postgres cluster
    Then backup bucket should exist with new files
    When application inserts 3 batches of test data
    Given empty master and slaves
    Then reading from postgres service url should fail
    When I restore backup to a postgres cluster
    Then reading from postgres service url should work
    Then last committed batch - 3 - should be visible

  @loadtest
  Scenario: Full backup, add data, restore
    Given a fresh postgres cluster
    When application inserts 4 batches of test data
    Then last committed batch - 4 - should be visible
    Given empty backup bucket
    When I run full backup
    Then backup bucket should exist with new files
    When application inserts 1 batches of test data
    Given empty master and slaves
    Then reading from postgres service url should fail
    When I restore backup to a postgres cluster
    Then reading from postgres service url should work
    Then last committed batch - 5 - should be visible

  @loadtest
  Scenario: Point in time recovery
    Given empty backup bucket
    Given a fresh postgres cluster
    When application inserts 2 batches of test data
    When I memorize current time for later PIT recovery
    When application inserts 3 batches of test data
    Then last committed batch - 5 - should be visible
    Given empty master and slaves
    When I restore backup to a postgres cluster with remembered PIT
    Then last committed batch - 2 - should be visible

