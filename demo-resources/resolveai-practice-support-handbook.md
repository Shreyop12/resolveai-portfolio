# ResolveAI Practice Support Handbook

## Enterprise SSO access troubleshooting

Use this guidance when an employee cannot sign in through their company SSO provider and receives an access denied or SAML configuration error.

1. Confirm that the customer’s company domain is verified in the ResolveAI workspace.
2. Ask an authorized workspace administrator to compare the identity provider’s SAML metadata with the workspace SSO configuration. Both the entity ID and certificate must match.
3. Confirm that the employee is assigned to the correct identity-provider application.
4. After an administrator saves a corrected configuration, the employee should sign out, wait five minutes, and try again.

Do not ask customers to send private keys, passwords, full authentication tokens, or unredacted identity-provider logs. If configuration still fails after these checks, collect the time of the failure and a redacted error code, then route the case to the identity team.

## Billing and subscription support policy

Workspace administrators can view invoices and plan details in Billing settings. To download an invoice, an administrator opens Billing settings, selects an invoice, and chooses Download PDF.

Support can explain available plans and invoice locations, but cannot change a customer’s plan, issue a refund, alter payment information, or disclose payment details. Requests for refunds, cancellations, plan changes, duplicate charges, or payment-method changes must be routed to a billing specialist for human review.

If an invoice is missing, ask the administrator to confirm the billing email address and the invoice month. Do not ask for a full card number, bank-account details, or tax identification number in a support ticket.

## Account and security support boundaries

Support may help an authorized workspace administrator locate account settings, verify that a domain is connected, or understand documented sign-in troubleshooting steps.

Support must escalate requests involving account deletion, password resets, administrator-role changes, API-key creation or rotation, suspected compromise, data export, privacy requests, security incidents, or requests to bypass authentication. Do not ask customers to share passwords, one-time codes, private keys, or session tokens.

For a suspected security incident, acknowledge the report, request only the incident time and a high-level description, and route the ticket to the security response team. Do not promise a resolution time or confirm that an account is compromised.
