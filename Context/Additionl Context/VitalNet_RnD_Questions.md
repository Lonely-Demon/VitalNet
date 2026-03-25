# VitalNet R&D — Research Questions
### Complete Question Bank for Architecture, Decision Rationale & Technical Analysis

---

## All Questions

1. Who exactly is the end user — what is their technical literacy, their device, their connectivity reality?
2. Why are we building this specific slice out of the entire VitalNet vision?
3. Why is this specific slice better than other possible slices we could have built?
4. Is there any existing solution similar to the slice we are working on?
5. If yes — what are its capabilities, and what are its drawbacks or what does it not cover?
6. If no — why does nothing like this exist?
7. If something existed and failed — why did it fail, what went wrong, and what can we learn from those mistakes?
8. What tech stack are we going to use for this specific slice?
9. Why that specific stack?
10. What are the other potential, viable options that could be used?
11. What were the factors that decided the final tech stack?
12. What were the other potential, viable options that were considered?
13. What were the strengths and weaknesses of the considered options based on the factors considered?
14. Choosing each stack offered what that other options didn't?
15. Choosing each stack had what drawback that ruled it out in favor of another alternative?
16. Who exactly is the end user — what is their technical literacy, their device, their connectivity reality?
17. What does the current manual workflow look like step by step — and where exactly does it break?
18. What is the cost of the current failure — in time, in lives, in missed diagnoses?
19. What is the minimum demoable unit of the slice — what does "working" look like in 24 hours?
20. What does the slice NOT do — and why is that a conscious decision, not a limitation?
21. How does this slice enable the rest of the vision — what does it unlock for future phases?
22. Why is a general-purpose LLM the right reasoning engine here — why not a purpose-built medical model?
23. What are the failure modes of LLM-based medical reasoning — and how does the system handle them?
24. What is the prompt engineering strategy — how is the medical context structured and why?
25. What guardrails exist to prevent dangerous outputs reaching an ASHA worker or doctor?
26. What is being simulated or mocked in the hackathon build — and what is genuinely working?
27. What is the single most likely point of failure during the demo — and what is the fallback?
28. What would a real production version need that this prototype doesn't have?
29. What real-world data exists about the scale of the problem — ASHA worker numbers, PHC load, rural patient statistics?
30. What is the measurable difference VitalNet makes to one patient interaction — in time, in accuracy, in outcome?
31. How do doctors use existing AIs?
32. How effective are existing AIs that doctors use?
33. For what specific tasks do doctors use existing AIs?
34. What is the difference between how a trained doctor uses an LLM and how an untrained ASHA worker would use one — and why does that gap matter?
35. When doctors use LLMs for diagnosis assistance, what information do they feed it — and how does that inform VitalNet's intake form design?
36. What do doctors say is missing from current LLM medical tools — what do they wish it could do?
37. Why would a doctor trust an AI-generated patient briefing — what makes the output credible enough to act on?
38. Why would an ASHA worker use this tool consistently — what makes it simple enough to not abandon after day one?
39. What happens when the AI is wrong — who is accountable and how does the system communicate uncertainty?
40. What connectivity can we realistically assume in rural India — 2G, 3G, 4G, or offline-first?
41. What language does an ASHA worker operate in — and does that affect the input and output design?
42. What device does an ASHA worker actually carry — smartphone, feature phone, tablet?

---

## Additional Suggested Questions (Accepted into bank)

43. What is the realistic data privacy expectation of a rural patient — and how does the prototype handle patient data even at demo stage?
44. How does the system behave when vitals or symptoms are incomplete — does it refuse, estimate, or flag uncertainty?
45. What is the latency budget for the full workflow — from ASHA worker input to doctor receiving the briefing — and is it achievable with free-tier APIs?
46. How does the AI briefing get delivered to the doctor — push notification, dashboard, SMS — and why that specific channel?
47. What does the triage output actually look like — what information does it contain, in what format, and why that format?
48. What stops this from being just another chatbot — what makes VitalNet structurally different from an ASHA worker simply texting a doctor on WhatsApp with ChatGPT open?

---

## Questions Grouped by Category

### Group 1 — Problem Depth
Q1, Q16, Q17, Q18, Q29, Q30

### Group 2 — Slice Definition
Q2, Q3, Q19, Q20, Q21

### Group 3 — Competitive Landscape
Q4, Q5, Q6, Q7

### Group 4 — How Doctors Use AI
Q31, Q32, Q33, Q35, Q36

### Group 5 — AI Layer Design
Q22, Q23, Q24, Q25, Q34

### Group 6 — Trust & Adoption
Q37, Q38, Q39

### Group 7 — India-Specific Reality
Q40, Q41, Q42, Q43

### Group 8 — Tech Stack
Q8, Q9, Q10, Q11, Q12, Q13, Q14, Q15

### Group 9 — Feasibility & Honesty
Q26, Q27, Q28, Q44, Q45

### Group 10 — Output & Delivery Design
Q46, Q47, Q48

### Group 11 — Impact
Q29, Q30
