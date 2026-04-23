# Employee Leave Management System Report

## Workflow Diagram

```mermaid
flowchart TD
    A[Employee submits leave request] --> B[System validates dates, overlap, and balance]
    B --> C[Request saved as PENDING]
    C --> D[Manager views department pending queue]
    D --> E[Approve]
    D --> F[Reject]
    E --> G[Deduct leave balance and mark APPROVED]
    F --> H[Keep balance unchanged and mark REJECTED]
    G --> I[Employee may cancel before start date]
    I --> J[Restore leave balance and mark CANCELLED]
```

## ER Diagram

```mermaid
erDiagram
    Department ||--o{ Employee : has
    Department ||--o| Employee : head
    Employee ||--o{ LeaveBalance : owns
    Employee ||--o{ LeaveRequest : submits
    Employee ||--o{ LeaveRequest : reviews
    LeaveType ||--o{ LeaveBalance : categorizes
    LeaveType ||--o{ LeaveRequest : categorizes
```

## Demo Credentials

- Admin: `admin@leavehub.local` / `Admin@12345`
- Manager: `nandhini.v.2367@gmail.com` / `Demo@12345`
- Employee: `poorni@gmail.com` / `Demo@12345`

## Balance Deduction and Restoration

- Approval locks the request and matching `LeaveBalance` record in a transaction, validates balance again, then increments `used_days`.
- Cancelling an approved leave before its start date decrements `used_days` by `num_days`, restoring the employee's remaining balance.
- Pending-request cancellation changes only the request status and does not touch balances.

## Screenshots Checklist

- Employee dashboard: `/`
- Manager approval panel: `/`
- Admin console: `/admin/`
- API endpoints: use Django browsable responses or Postman on `/api/...`

## Git Log

- The current execution environment did not have Git CLI available, so commit history could not be generated from within this workspace.
