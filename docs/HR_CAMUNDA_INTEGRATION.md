# HR Camunda Integration

The existing Workflow port is reused. HR records store only workflow instance references and current projection data. Callbacks validate correlation, process definition/version, expected state and idempotency before transition. Human work remains in the shared Task service.

Leave, changes, termination and offboarding may integrate with approved process definitions. Add Employee must not start Camunda, create tasks or publish workflow commands in this scope.
