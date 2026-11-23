"""Standard wording for client agreements: the Master Services Agreement (MSA) and the Managed Services schedule.

Same simple format as the other legal texts: "## " heading, "- " bullet, blank line = new paragraph, {placeholders}
filled in when the agreement is built. The MSA wording can be changed in Settings › Legal & terms; the service
descriptions below are picked per contract in the contract builder.

These are starting drafts for your business, not legal advice — have an attorney review them before relying on them.
"""

MSA = """## Master Services Agreement
This Master Services Agreement (the "Agreement") is between {company} ("{company_short}", "we", "us") and {client} ("Client", "you"). It takes effect on {effective_date} (the "Effective Date") and sets the terms for all services we provide to you.{entities_line}

## 1. How this Agreement works
- This Agreement contains the general terms. The specific services, prices and term are described in one or more service schedules, statements of work, or accepted quotes (each a "Schedule").
- Each Schedule becomes part of this Agreement when both parties sign or accept it. If a Schedule and this Agreement disagree, the Schedule controls for the services it covers, but only where it says it is changing this Agreement.
- Work you ask for that is not covered by a Schedule is billed at our standard rates in effect at the time.

## 2. Our services
- We will perform the services in a professional and workmanlike manner, using people with the skills the work requires.
- We may use subcontractors and third-party tools to deliver the services. We remain responsible for work performed by our subcontractors.
- Response and resolution times in a Schedule are targets, not guarantees, unless the Schedule says otherwise.

## 3. Your responsibilities
- Give us timely access to your premises, systems, staff and information as reasonably needed to do the work.
- Name a primary contact who can make decisions and approve work and charges for you.
- Keep your systems in a supportable state: hardware under warranty or reasonably current, operating systems and software supported by their makers, and properly licensed.
- Follow reasonable security recommendations we make. If you decline a recommendation, you accept the risk that results from that choice, and we are not responsible for problems the recommendation would have prevented.
- Tell us promptly about any suspected security incident, and about changes to your staff, locations or systems that affect the services.
- Do not send us passwords, payment card numbers, health records or other sensitive personal information by email or in service requests. Use the secure method we give you.

## 4. How to ask for service
- Every service request must come to us in one of three ways: (1) by calling our help desk{help_phone}; (2) by email to {support_email}; or (3) by opening a service ticket in the {portal_name} help desk system.
- We do not take service requests by text message. You agree that you and your staff will not text or call our technicians' cell phones for service. A request made that way is not a service request: it is not tracked, and no response time applies to it.
- Do not put usernames, passwords, or any personal, financial or health information (including personally identifiable information and information protected by HIPAA) in a ticket, an email or an attachment. We are not responsible for information sent to us in a way this section prohibits, or for the consequences of a client not following this section.
- For emergencies outside support hours, such as a server being down, call our after-hours number{after_hours_phone}. There is a charge for using this number: calls to it are billed at our after-hours rates unless a Schedule says otherwise.
- When you call the help desk we try to fix the problem before the call ends. Sometimes we will need to call you back to finish the work.
- Level 1 tickets are routine issues that do not stop your business from operating. We try to fix them by the end of the business day they come in, and we have up to 24 hours to fix any Level 1 ticket that does not affect your ability to do business.

## 5. Fees and payment
- You will pay the fees shown in each Schedule and on our invoices. Recurring fees are billed in advance; hourly work, projects, hardware and software are billed as delivered or as quoted.
- Invoices are due {net_terms_text}. {late_policy}
- If an account is referred for collection, you agree to pay the reasonable costs of collecting it, including collection agency fees, court costs and reasonable attorneys' fees, to the extent allowed by law.
- Tell us in writing (email {billing_email}) about any billing question within {dispute_days} days of the invoice date. Any part of an invoice that is not in question remains due on time.
- We may pause non-emergency services on an account that is more than {suspend_days} days past due, after giving you notice. Fees continue to accrue during a suspension.
- Prices do not include sales or other taxes unless shown. You are responsible for taxes on what you buy, other than taxes on our income.
- We may change recurring fees at the start of any renewal term by giving you at least 30 days' written notice, and during a term if your number of users, devices or locations changes or a vendor raises the price of a product we resell to you.

## 6. Term and ending this Agreement
- This Agreement starts on the Effective Date and continues until every Schedule has ended and either party ends this Agreement with {notice_days} days' written notice.
- Each Schedule has its own term and renewal, stated in that Schedule.
- Either party may end this Agreement or a Schedule if the other materially breaches it and does not fix the breach within 30 days after written notice (10 days for non-payment).
- {company_entities_cap} may stop all services and cancel this Agreement and every Schedule immediately, by written notice, if you or your staff are abusive, threatening or harassing toward our people; if you are unwilling to resolve problems we have identified in your systems; or if you do not follow {company}'s policies, including the rules in Section 4. Fees for services provided up to that date remain due.
- If you end a Schedule early without cause, or we end it because of your breach, the fees for the rest of its current term become due, unless the Schedule says otherwise.
- Ending this Agreement does not cancel amounts already owed.

## 7. Cancelling at your request, and moving to another provider
- We do not accept a cancellation by phone. To cancel, send an email to {cancel_email} with a letter on your company letterhead that gives your account number and the date you want service to end. The rest of this Agreement, including any notice period and fees for the remainder of a term, still applies.
- {company_entities_or_cap} will start processing your request the same business day we receive it, and we will keep providing service up to the cancellation date.
- We will release to you all passwords for the equipment and accounts you own. We will also remove our monitoring and management software and our own access, and give you a copy of the records we keep about your environment.
- If your new IT company needs our help moving things over, that work is billed at {transition_rate} per hour.
- If your new IT company is not ready to take over by the cancellation date and you ask us to keep supporting you, you agree to pay {post_cancel_rate} for any IT support we provide after that date. That work is billed as off-contract work.
- We cannot call your new IT company and speak for you. You need to be on the call with us as a three-way call.
- Software, licenses and security tools that we provide as part of our services stop on the cancellation date unless you arrange to take them over with the vendor.

## 8. Third-party products and services
- Hardware, software and cloud services made by others are provided under the maker's own terms and warranty. We pass those through to you and will help you use them, but we do not add to them.
- You authorize us to act as your agent in dealing with your vendors for the services, and to accept routine license terms and updates on your behalf where needed to keep your systems working.
- We are not responsible for outages, defects, price changes or the discontinuation of third-party products and services.

## 9. Security, backups and data
- Our role is to secure your systems and to give you feedback on ways to protect yourself. You agree to follow {company}'s cybersecurity recommendations.
- To the fullest extent the law allows, you will hold {company_entities_cap} harmless from any claim arising out of a data breach or other security incident involving your systems or data.
- No security measure can prevent every attack. We do not guarantee that your systems will be free of viruses, ransomware, intrusion, data loss or downtime, and we are not liable for a security incident unless it was directly caused by our gross negligence or willful misconduct.
- Unless a Schedule includes a managed backup service, you are responsible for backing up your data. Where we do manage backups, we monitor them and act on failures, but we cannot guarantee that every file can be restored.
- Responding to and recovering from a security incident, a disaster, or a problem caused by something outside the covered services is not included in recurring fees and is billed at our standard rates unless a Schedule says otherwise.
- Your data remains yours. We access it only as needed to provide the services.
- If you are subject to HIPAA or similar rules and we may have access to protected information, the parties will sign a separate Business Associate Agreement. Meeting the regulatory requirements that apply to your business remains your responsibility.

## 10. Confidentiality
- Each party will keep the other's non-public business, technical and financial information confidential, use it only to perform this Agreement, and protect it with at least reasonable care.
- This does not apply to information that is public, was already known, is independently developed, or must be disclosed by law (after notice to the other party where allowed).
- These duties continue for three years after this Agreement ends, and for as long as the information remains a trade secret.

## 11. Ownership
- You own your data and the systems and licenses you pay for.
- We own our tools, scripts, methods, documentation templates and know-how, including improvements made while serving you. You may use the documentation we prepare about your environment for your own internal purposes.

## 12. Our people
- During this Agreement and for 12 months after it ends, neither party will hire or solicit for hire an employee of the other who was involved in the services, without the other's written consent. General job postings not aimed at those employees are not a breach.
- If a party breaches this section, it will pay the other an amount equal to 50% of the employee's first-year compensation as a reasonable estimate of the cost of replacing that person, not as a penalty.

## 13. Warranty disclaimer
EXCEPT AS STATED IN THIS AGREEMENT, {company_upper} MAKES NO OTHER WARRANTIES, EXPRESS OR IMPLIED, INCLUDING ANY IMPLIED WARRANTY OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE OR NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICES OR YOUR SYSTEMS WILL BE UNINTERRUPTED, ERROR-FREE OR COMPLETELY SECURE.

## 14. Limitation of liability
- TO THE EXTENT ALLOWED BY LAW, NEITHER PARTY IS LIABLE TO THE OTHER FOR INDIRECT, INCIDENTAL, SPECIAL, PUNITIVE OR CONSEQUENTIAL DAMAGES, OR FOR LOST PROFITS, LOST REVENUE, LOST OR CORRUPTED DATA, OR BUSINESS INTERRUPTION, EVEN IF TOLD THEY WERE POSSIBLE.
- TO THE EXTENT ALLOWED BY LAW, {company_upper}'S TOTAL LIABILITY ARISING OUT OF THIS AGREEMENT WILL NOT EXCEED THE FEES YOU PAID US FOR THE SERVICES THAT GAVE RISE TO THE CLAIM IN THE {liability_months} MONTHS BEFORE THE EVENT THAT CAUSED IT.
- These limits do not apply to your obligation to pay fees, to a party's breach of its confidentiality duties, or to damages caused by a party's willful misconduct.
- Any claim must be brought within one year after the party knew, or reasonably should have known, of the facts behind it.

## 15. Indemnification
- You will defend and indemnify us against third-party claims arising from your data, your unlicensed or illegal use of software or systems, or your violation of law.
- We will defend and indemnify you against third-party claims that our own work product infringes that party's intellectual property rights.
- The party seeking protection must give prompt notice of the claim, allow the other to control the defense, and cooperate reasonably.

## 16. Insurance
Each party will carry insurance appropriate to its business. We carry commercial general liability and technology errors and omissions coverage and will provide a certificate on request. We recommend that you carry cyber liability insurance; this Agreement is not a substitute for it.

## 17. Events outside our control
Neither party is responsible for a delay or failure caused by events beyond its reasonable control, such as natural disasters, power or internet outages, failures of third-party services, cyberattacks on third parties, labor disputes, or government action. This does not excuse payment for services already delivered.

## 18. Independent contractor
We are an independent contractor. Nothing in this Agreement creates a partnership, joint venture or employment relationship between the parties.

## 19. Notices
Notices under this Agreement must be in writing and sent by email to the other party's primary business contact, with a copy by mail for a notice of breach or termination. Our address for notices is {company_address}; email {support_email}.

## 20. Governing law and disputes
- This Agreement is governed by the laws of the State of {state}, without regard to its conflict-of-law rules.
- The parties will first try in good faith to resolve any dispute by talking between people with authority to settle it.
- Any lawsuit will be brought in the state or federal courts located in {county} County, {state}, and each party consents to those courts. The prevailing party in a lawsuit to enforce this Agreement is entitled to its reasonable attorneys' fees and costs.

## 21. General
- This Agreement, together with its Schedules, is the entire agreement between the parties about its subject and replaces earlier discussions and proposals.
- Changes must be in writing and accepted by both parties. Our routine notices of price changes under Section 5 take effect as stated there.
- Neither party may assign this Agreement without the other's consent, except to a successor to its business.
- If part of this Agreement is found unenforceable, the rest stays in effect. Not enforcing a right is not a waiver of it.
- Sections that by their nature should continue after this Agreement ends (including fees owed, confidentiality, ownership, limits of liability and governing law) do continue.

## 22. Electronic signatures
The parties agree that this Agreement and its Schedules may be signed electronically, that a typed name entered on our signing page is that person's signature, and that an electronic copy is an original. The person signing for each party confirms they have authority to bind that party.
"""

# The Managed Services schedule. {services}, {pricing}, {support}, {exclusions} are built from what was picked in the builder.
MSP_SCHEDULE = """## Managed Services Schedule
This Schedule is between {company} and {client} and describes the managed IT services we will provide. {msa_line}

## 1. Term
- Start date: {start_text}.
- Initial term: {term_text}.
- Renewal: {renewal_text}
- To stop a renewal, either party gives written notice at least {notice_days} days before the current term ends.
{increase_line}

## 2. What is covered
{covered_intro}

{services}

## 3. Support hours and response targets
{support}

## 4. Fees
{pricing}

## 5. What is not covered
The following are outside the monthly fee and, when you ask for them, are quoted or billed at the rates in Section 4:

{exclusions}

## 6. Changes in your environment
- We review the number of users, devices and locations regularly. When they change, the monthly fee changes with them from the next invoice, at the unit prices in Section 4.
- Bringing a new user, computer or location onto the service may carry a one-time setup charge, which we will quote first.
- Systems that do not meet the minimum standards in the Agreement are supported on a best-effort basis, and work on them may be billed hourly, until they are brought up to standard.

## 7. Ending this Schedule
- Either party may end this Schedule as described in the Agreement.
- {early_line}
- When this Schedule ends we will carry out the transition steps in the Agreement.
"""

# key: (short name, what the client is told). Order is the order they print in.
SERVICES = [
    ("help_desk", "Help desk", "{unlimited}emote help desk support for covered users during support hours, by phone, email and the client portal."),
    ("onsite", "Onsite support", "Onsite visits to your covered locations when a problem cannot be fixed remotely."),
    ("monitoring", "Monitoring and patching", "24/7 monitoring of covered computers and servers, with operating system and common application updates applied on a regular schedule."),
    ("security", "Endpoint security", "Managed antivirus / endpoint protection on covered computers and servers, with alerts reviewed and acted on."),
    ("backup", "Managed backup", "Backup of the servers and data listed in this Schedule, monitored daily, with failed backups investigated and test restores performed periodically."),
    ("email_admin", "Microsoft 365 / Google Workspace administration", "Adding, changing and removing user accounts, mailboxes, licenses, groups and security settings in your tenant."),
    ("network", "Network management", "Management of your firewall, switches and Wi-Fi: configuration, firmware updates and troubleshooting."),
    ("vendor", "Vendor management", "We deal with your internet, phone, printer and line-of-business software vendors on your behalf for support issues."),
    ("users", "User onboarding and offboarding", "Setting up new staff and securely removing access for staff who leave, on request from your authorized contact."),
    ("training", "Security awareness training", "Online security awareness training and simulated phishing tests for your staff, with results reported to you."),
    ("documentation", "Documentation and inventory", "An up-to-date record of your network, devices, accounts and licenses, available to you on request."),
    ("reviews", "Technology reviews", "A regular review meeting covering the health of your systems, recurring issues, upcoming renewals and budget planning."),
    ("after_hours", "After-hours emergency support", "Emergency support outside support hours for issues that stop your business from operating."),
]
SERVICE_DEFAULTS = ["help_desk", "monitoring", "security", "email_admin", "network", "vendor", "users", "documentation"]

EXCLUSIONS = [
    "Hardware, software, licenses, subscriptions and cloud services (quoted separately).",
    "Projects, such as new servers, office moves, migrations, new locations, major upgrades and new system roll-outs.",
    "Response to and recovery from security incidents, ransomware, data breaches and disasters.",
    "Work on equipment or software that is out of warranty, no longer supported by its maker, or not licensed.",
    "Problems caused by changes made by anyone other than us, by misuse, or by events outside our control.",
    "Home networks and personally owned devices, unless listed in this Schedule.",
    "Software development, website work, and training on line-of-business applications.",
    "Compliance audits, assessments and legal or regulatory advice.",
]

# The hourly (break/fix) schedule: no monthly fee, work is done on request and billed by the hour.
HOURLY_SCHEDULE = """## Hourly Services Schedule
This Schedule is between {company} and {client} and describes IT services we provide on request, billed by the hour. {msa_line}

## 1. How it works
- There is no monthly fee and no minimum commitment. You ask for help when you need it, and we bill for the time and materials used.
- We do not monitor, patch, back up or secure your systems under this Schedule. Those are managed services and are available under a separate schedule.
- We schedule hourly work as our calendar allows. Clients with a managed services agreement are served first.

## 2. Rates
{pricing}

## 3. Support hours and response targets
{support}

## 4. Approving the work
- For anything beyond a simple fix we will tell you what we expect it to take before we start, and get your go-ahead if it grows.
- When the work is finished we ask your contact to confirm it is complete and to acknowledge the time and charges. That confirmation is our record that the work was accepted.
- Hardware, software and licenses are quoted separately and ordered once you approve the quote.

## 5. What you are responsible for
- Keeping current backups of your data. We are not responsible for data lost on systems we were not engaged to back up.
- Keeping your systems licensed, under warranty and supported by their makers.
- Deciding whether to follow our recommendations. If you decline one, you accept the risk that results.

## 6. Term
- This Schedule starts on {start_text} and continues until either party ends it with {notice_days} days' written notice.
- We may change our hourly rates with 30 days' written notice.
- Ending this Schedule does not cancel charges for work already done.
"""

# Business Associate Agreement, following the elements in 45 CFR 164.504(e) and the HHS sample provisions.
BAA = """## Business Associate Agreement
This Business Associate Agreement (the "BAA") is between {client} ("Covered Entity") and {company} ("Business Associate"). It takes effect on {effective_date} and applies whenever Business Associate creates, receives, maintains or transmits protected health information for Covered Entity while providing IT services (the "Services").

## 1. Definitions
- "HIPAA Rules" means the Privacy, Security, Breach Notification and Enforcement Rules at 45 CFR Parts 160 and 164, as amended.
- "Protected Health Information" or "PHI" has the meaning given in 45 CFR 160.103, limited to the information Business Associate handles for Covered Entity.
- Other terms used here that are defined in the HIPAA Rules have the meanings given there.

## 2. What Business Associate may do with PHI
- Business Associate may use and disclose PHI only as needed to provide the Services, as required by law, and as this BAA permits. Its access to PHI is incidental to maintaining and supporting Covered Entity's systems.
- Business Associate will limit its use, disclosure and requests for PHI to the minimum necessary for the task.
- Business Associate may use PHI for its own proper management and administration and to carry out its legal responsibilities, and may disclose PHI for those purposes if the disclosure is required by law, or if the recipient gives reasonable assurances that it will keep the PHI confidential, use it only for the purpose it was disclosed, and report any breach of confidentiality to Business Associate.
- Business Associate will not use or disclose PHI in a way that would violate Subpart E of 45 CFR Part 164 if done by Covered Entity, except as allowed in the paragraph above.

## 3. Business Associate's obligations
- Not use or disclose PHI other than as permitted by this BAA or as required by law.
- Use appropriate safeguards, and comply with Subpart C of 45 CFR Part 164 for electronic PHI, to prevent use or disclosure not provided for by this BAA.
- Report to Covered Entity any use or disclosure of PHI not provided for by this BAA of which it becomes aware, including any breach of unsecured PHI as required by 45 CFR 164.410, and any security incident. A breach will be reported without unreasonable delay and no later than {breach_days} days after Business Associate discovers it, with the information Covered Entity needs for its own notices to the extent Business Associate has it.
- Unsuccessful attempts, such as pings, port scans and blocked log-in attempts that do not result in access to PHI, are reported by this notice and need no further report.
- Ensure, in line with 45 CFR 164.502(e)(1)(ii) and 164.308(b)(2), that any subcontractor that creates, receives, maintains or transmits PHI for Business Associate agrees to the same restrictions and conditions that apply to Business Associate.
- Make PHI in a designated record set available to Covered Entity as needed for Covered Entity to meet its obligations under 45 CFR 164.524, within 15 days of a request, to the extent Business Associate holds it.
- Make amendments to PHI in a designated record set as directed by Covered Entity under 45 CFR 164.526, to the extent Business Associate holds it.
- Keep and make available the information needed for Covered Entity to give an accounting of disclosures under 45 CFR 164.528.
- To the extent Business Associate carries out an obligation of Covered Entity under Subpart E of 45 CFR Part 164, comply with the requirements that apply to Covered Entity in doing so.
- Make its internal practices, books and records relating to PHI available to the Secretary of Health and Human Services for determining compliance with the HIPAA Rules.

## 4. Covered Entity's obligations
- Tell Business Associate of any limitation in its notice of privacy practices, any change in or revocation of an individual's permission, and any restriction it has agreed to, where these affect Business Associate's use or disclosure of PHI.
- Not ask Business Associate to use or disclose PHI in a way that would not be permitted under the HIPAA Rules if done by Covered Entity.
- Give Business Associate only the access to PHI that the Services require, and not send PHI to Business Associate by email, in service requests or in screenshots.
- Remain responsible for its own compliance with the HIPAA Rules, including its risk analysis, policies, workforce training and the security settings it chooses for its systems.

## 5. Term and termination
- This BAA stays in effect for as long as Business Associate provides the Services, and ends when the Services end or when it is terminated under this section.
- Covered Entity may terminate this BAA, and the Services that involve PHI, if Business Associate materially violates it and does not cure the violation within 30 days after written notice.
- When this BAA ends, Business Associate will return or destroy the PHI it still holds, where that is feasible, and keep no copies. Where return or destruction is not feasible (for example, PHI in backups kept for a retention period), Business Associate will continue to protect that PHI under this BAA and limit its use to the purposes that make return or destruction infeasible, for as long as it holds it.
- The obligations in this section continue after this BAA ends.

## 6. General
- If the parties have a services agreement, this BAA is part of it. Where this BAA and that agreement disagree about PHI, this BAA controls. The limits of liability in that agreement apply to this BAA to the extent the law allows.
- A reference in this BAA to a section of the HIPAA Rules means the section as in effect or as amended.
- The parties will amend this BAA as needed for both to comply with the HIPAA Rules and other applicable law.
- Any ambiguity in this BAA will be read in the way that permits compliance with the HIPAA Rules.
- Nothing in this BAA gives rights to anyone other than the parties.
- This BAA is governed by federal law and, where federal law does not apply, by the laws of the State of {state}.
- The parties agree that this BAA may be signed electronically and that a typed name entered on the signing page is that person's signature.
"""
