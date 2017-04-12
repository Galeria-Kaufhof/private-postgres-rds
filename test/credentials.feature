Feature: providing access to development teams
  Scenario: admin password should not be reset on provisioning
    Given a fresh postgres cluster
    When user changes admin password to Fo0baR
    When I initialize postgres cluster to refresh
    Then user can access database with password Fo0baR
