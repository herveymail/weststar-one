"""Built-in drafts of the legal texts (see apps/core/legal.py). No imports here: settings_catalog loads it early."""

RELEASED = "2026-11-10"  # "last updated" for the built-in drafts until someone edits them

INVOICE_TERMS = """## Terms & Conditions
These terms apply to the services and products on this invoice. If {company} and you have a signed services agreement, that agreement controls where it differs from these terms.

## Payment
Payment is due by the due date shown on this invoice. You can pay online by card or bank account (ACH) using the "View & pay invoice" link, or by check made payable to {company}. Card and bank payments are processed by Stripe; {company} does not store your full card or bank account numbers.

## Late payment
{late_policy}

## Collection costs
If an account is referred for collection, you agree to pay the reasonable costs of collecting it, including collection agency fees, court costs and reasonable attorneys' fees, to the extent allowed by law. Accounts more than 30 days past due may be referred to a collection agency.

## Returned payments
A payment returned or reversed by your bank (including an ACH return or a card chargeback that is resolved in our favor) will be added back to your balance together with a returned-payment fee of up to the amount allowed by {state} law.

## Suspension of service
{company} may pause non-emergency services on an account that is more than {suspend_days} days past due, after giving notice. Services resume once the account is brought current.

## Billing questions and disputes
Please tell us in writing (email {billing_email}) about any billing question within {dispute_days} days of the invoice date. Charges not questioned within that time are considered accepted. Any part of an invoice that is not in question remains due on time.

## Taxes
Prices do not include sales or other taxes unless shown. You are responsible for taxes on the services and products you buy, other than taxes on {company}'s income.

## Warranty
Services are performed in a professional and workmanlike manner. Hardware and software made by others carry only the manufacturer's warranty, which {company} will help you use. EXCEPT AS STATED HERE, {company_upper} MAKES NO OTHER WARRANTIES, EXPRESS OR IMPLIED, INCLUDING ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.

## Your data and backups
Unless you have a managed backup service with {company}, you are responsible for keeping current backups of your data. {company} is not responsible for data lost on systems that were not backed up.

## Limitation of liability
TO THE EXTENT ALLOWED BY LAW, {company_upper} IS NOT LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL OR CONSEQUENTIAL DAMAGES, OR FOR LOST PROFITS, LOST DATA OR BUSINESS INTERRUPTION, AND ITS TOTAL LIABILITY RELATING TO THIS INVOICE WILL NOT EXCEED THE AMOUNT OF THIS INVOICE.

## Governing law
These terms are governed by the laws of the State of {state}. Any dispute will be heard in the state or federal courts located in {county} County, {state}.
"""

QUOTE_TERMS = """## Terms & Conditions
This quote becomes an agreement between you and {company} when you accept it (by signing, approving it online or paying the deposit). If you have a signed services agreement with {company}, that agreement controls where it differs from these terms.

## Price and validity
Prices are good for {quote_valid_days} days from the quote date. Hardware and software prices depend on our suppliers and may change before an order is placed; we will tell you before ordering if a price goes up.

## Deposit and payment
{deposit_line} The remaining balance is invoiced when the work is complete and is due under the invoice terms. Late payment is subject to the late fees and collection terms on our invoices.

## Scope and changes
The quote covers only the work described. Additional work, changes you request, or conditions we could not reasonably see beforehand (for example damaged cabling, missing licenses or failed hardware) will be quoted separately or billed at our standard rates after you approve them.

## Scheduling and access
You agree to give {company} reasonable access to your site, systems and the people needed to finish the work. Delays caused by lack of access may change the schedule and the price.

## Products and ownership
Ownership of hardware passes to you when it is paid for in full. Special-order items may not be returnable once ordered; returnable items may carry the supplier's restocking fee.

## Warranty
Work is performed in a professional and workmanlike manner. Products made by others carry only the manufacturer's warranty. EXCEPT AS STATED HERE, {company_upper} MAKES NO OTHER WARRANTIES, EXPRESS OR IMPLIED, INCLUDING ANY IMPLIED WARRANTY OF MERCHANTABILITY OR FITNESS FOR A PARTICULAR PURPOSE.

## Limitation of liability
TO THE EXTENT ALLOWED BY LAW, {company_upper} IS NOT LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL OR CONSEQUENTIAL DAMAGES, OR FOR LOST PROFITS, LOST DATA OR BUSINESS INTERRUPTION, AND ITS TOTAL LIABILITY RELATING TO THIS QUOTE WILL NOT EXCEED THE AMOUNT PAID UNDER IT.

## Governing law
These terms are governed by the laws of the State of {state}. Any dispute will be heard in the state or federal courts located in {county} County, {state}.
"""

PORTAL_TERMS = """## Client Portal Terms of Use
Last updated {updated}

These terms cover your use of the {company} client portal (the "Portal"). By signing in you agree to them on your own behalf and for the organization you work for. If your organization has a signed services agreement with {company}, that agreement controls where it differs from these terms.

## Your account
- Keep your password and sign-in codes private. Do not share your account; ask us for a separate account for each person.
- Tell us right away at {support_email} or {company_phone} if you think someone else has used your account.
- You are responsible for what is done with your account, and for making sure the information you give us is accurate.

## Using the Portal
- Use the Portal only to request and track support, review and sign documents, and other purposes connected with {company}'s services.
- Do not upload anything unlawful or harmful, try to reach accounts or data that are not yours, test or disrupt the Portal's security, or use automated tools to collect information from it.
- Do not send passwords, full card numbers or other highly sensitive information in tickets unless we ask you to use a secure method.

## Documents and signatures
When you approve a quote, sign a contract or acknowledge a policy in the Portal, you agree that your electronic approval or signature has the same effect as a handwritten one, and that we may keep an electronic record of it (including the date, time and the address you signed from).

## Messages from us
We send email about your tickets, documents and account. Where you have given us a mobile number for ticket updates, we may text it; message and data rates may apply, and you can reply STOP to stop texts.

## Availability
We work to keep the Portal available but do not promise it will always be available or error-free. Response times for support are set by your services agreement, not by the Portal. For an emergency, call {company_phone}.

## Your content and ours
You keep ownership of the information you send us; you let {company} use it to provide services to you. The Portal itself, and our documents and content in it, belong to {company}.

## Ending access
We may suspend or end Portal access for misuse, for security reasons or when our services to your organization end. Your organization can ask us to remove a user at any time.

## Limitation of liability
TO THE EXTENT ALLOWED BY LAW, THE PORTAL IS PROVIDED "AS IS", AND {company_upper} IS NOT LIABLE FOR INDIRECT, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING FROM YOUR USE OF IT.

## Changes
We may update these terms. If we make a change, we will ask you to agree to the new version the next time you sign in.

## Governing law
These terms are governed by the laws of the State of {state}, and any dispute will be heard in {county} County, {state}.

## Contact
{company}, {company_address}. {support_email} · {company_phone}
"""

PRIVACY = """## Privacy Policy
Last updated {updated}

This policy explains how {company} handles information about our clients and the people who use our client portal, pay our invoices or contact our help desk.

## What we collect
- Contact details: names, job titles, email addresses, phone numbers and business addresses.
- Support information: what you send in tickets, emails and calls, files you upload, and notes our technicians make while helping you.
- Technical information about the computers, networks and accounts we manage for you, as needed to support them.
- Billing information: invoices, payments and the last four digits and type of the card or bank account used. Full card and bank numbers are entered on Stripe's secure page and are not stored by {company}.
- Portal records: when you sign in, the address you signed in from, and the documents you approve or sign.

## How we use it
- To provide, support and improve the services you buy from us.
- To send invoices, receipts, ticket updates and other service messages.
- To keep our systems and yours secure, and to meet legal, tax and accounting duties.
We do not sell your personal information, and we do not use it for advertising.

## Who we share it with
We share information only with companies that help us provide our services, under agreements that require them to protect it — for example our payment processor (Stripe), our email and productivity provider (Google Workspace), and the backup, remote-support and security tools we use to manage your systems. We may also share information when the law requires it, to protect our rights, or with a buyer if our business is sold.

## How we protect it
We use encrypted connections, encryption of sensitive data at rest, two-factor sign-in for staff, access limited to the people who need it, and activity logs. No system is perfectly secure; if a breach affects your personal information we will notify you as the law requires.

## How long we keep it
We keep support and billing records for as long as you are a client and afterwards for as long as needed for legal, tax and accounting purposes, then delete or de-identify them.

## Your choices
You can ask us for a copy of the personal information we hold about you, to correct it, or to delete what we are not required to keep, by emailing {support_email}. Your organization's administrator can also ask us to add or remove portal users.

## Contact
{company}, {company_address}. {support_email} · {company_phone}
"""

STAFF_CONFIDENTIALITY = """## Confidentiality & Acceptable Use
Last updated {updated}

{company} is trusted with our clients' systems, passwords and data. This agreement applies to everyone who signs in to Weststar ONE.

## Client and company information is confidential
- Information about our clients — their systems, passwords, data, users, finances and anything you see while working for them — is confidential. Use it only to do your job, and do not share it with anyone who does not need it for {company}'s work.
- The same applies to {company}'s own information: pricing, client lists, contracts, employee records and business plans.
- These duties continue after your employment or engagement ends.

## Passwords and access
- Store client and company credentials only in the company's password manager or in Weststar ONE. Never in personal notes, email, chat or browsers on personal devices.
- Do not share your own sign-in. Two-factor sign-in must stay on.
- Use your access only for work you have been asked to do. Do not look at client data out of curiosity.

## Company systems and devices
- Company systems, accounts and devices are for business use. Limited personal use is fine if it does not interfere with work or create risk.
- Do not install unapproved software on client systems, disable security tools, or connect unknown devices to client networks.
- Do not use company or client systems for anything unlawful, harassing or offensive.

## Monitoring
{company} may monitor, log and review the use of its systems and accounts, including Weststar ONE, email and remote-access tools, to protect clients and the company. Do not expect privacy in anything you do on company systems.

## Reporting problems
Report a lost or stolen device, a suspected security incident, or a mistake that exposed client data to a manager right away — within one hour if you can. Reporting quickly is always the right call.

## When you leave
Return all company and client property and credentials, and do not keep copies of client or company information.

Breaking this agreement may lead to discipline up to and including termination, and may also have legal consequences.
"""

HANDBOOK_ACK = """## Employee Handbook Acknowledgment
Last updated {updated}

I acknowledge that I have received and read (or have had the chance to read) the {company} employee handbook and policies{handbook_where}, and that I understand I should ask my manager or H/R about anything I do not understand.

I understand that:
- My employment with {company} is at will: either I or {company} may end it at any time, with or without cause or notice, unless a written agreement signed by an owner of {company} says otherwise.
- The handbook is a guide to policies and benefits; it is not a contract of employment, and {company} may change it at any time.
- I am expected to follow the handbook and policies as they are updated, and I will be asked to acknowledge important changes.
"""

DOCS = {
    # key: (title, default text, who it's for)
    "invoice_terms": ("Invoice terms & conditions", INVOICE_TERMS, "Printed on every invoice (page 2 of the PDF) and on the pay page."),
    "quote_terms": ("Quote terms & conditions", QUOTE_TERMS, "Printed on every quote (page 2 of the PDF) and on the quote page in the portal."),
    "portal_terms": ("Client portal terms of use", PORTAL_TERMS, "Clients agree to these on their first portal sign-in, and again after you change them."),
    "privacy": ("Privacy policy", PRIVACY, "Linked from the portal, the sign-in pages and the invoice pay page."),
    "staff_confidentiality": ("Staff confidentiality & acceptable use", STAFF_CONFIDENTIALITY, "Staff agree at sign-in, once a year and after you change it."),
    "handbook_ack": ("Employee handbook acknowledgment", HANDBOOK_ACK, "Staff acknowledge at sign-in, and again after you change it or the handbook link."),
}
