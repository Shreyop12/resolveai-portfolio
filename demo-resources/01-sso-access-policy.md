# Enterprise SSO access troubleshooting

Use this guidance when an employee cannot sign in through their company SSO provider and receives an access denied or SAML configuration error.

1. Confirm that the customer’s company domain is verified in the ResolveAI workspace.
2. Ask an authorized workspace administrator to compare the identity provider’s SAML metadata with the workspace SSO configuration. Both the entity ID and certificate must match.
3. Confirm that the employee is assigned to the correct identity-provider application.
4. After an administrator saves a corrected configuration, the employee should sign out, wait five minutes, and try again.

Do not ask customers to send private keys, passwords, full authentication tokens, or unredacted identity-provider logs. If configuration still fails after these checks, collect the time of the failure and a redacted error code, then route the case to the identity team.
