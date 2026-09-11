# CSM/CSAL V3 production-agent evidence questions

Use each question in a fresh production-agent conversation. The wording is frozen for this evidence run.

## E01

```text
For August 2026, what was the total booked TEU? Count each customer, agreement, reporting week, service and TCR combination once, even when it appears in more than one CSAL allocation category.
```

## E02

```text
For August 2026, what was the total reviewed commitment? Count it once for each customer, agreement, reporting week and service, rather than counting it again for every TCR or allocation category.
```

## E03

```text
For August 2026, what was the monthly reviewed TEU? Count each month, customer, sales representative, agreement and service combination once.
```

## E04

```text
Across the agreements shown for August 2026, what was the total SC MQC? Count each agreement once rather than once for every booking or allocation row.
```

## E05

```text
For August 2026, what was the total reviewed allocation TEU? Use the detailed allocation rows and tell me whether removing repeated booking information changes this allocation total.
```

## E06

```text
In August 2026, how many customer, agreement, reporting week, service and TCR combinations appeared in more than one allocation category? Also tell me how many of those combinations had more than one value for the volume without CSAL flag.
```

## E07

```text
In August 2026, how many customer, agreement, reporting week, service and TCR combinations had more than one days-to-cutoff value? Do not choose one cutoff value when the source contains different values.
```

## E08

```text
For August 2026, find the customer, agreement, reporting week and service combination that has the most TCRs. Show confirmed and booked TEU for each TCR, followed by one separate row containing its total reviewed commitment. Do not repeat or add that commitment for every TCR.
```

## E09

```text
For August 2026, what was the overall cancellation percentage? Calculate it from total cancelled TEU divided by total booked TEU after counting each customer, agreement, reporting week, service and TCR combination once. Do not average the stored row percentages.
```

## E10

```text
For August 2026, how many detailed allocation rows have a missing agreement, a missing sales representative, or both? Keep these records in the result and show the three groups separately.
```
