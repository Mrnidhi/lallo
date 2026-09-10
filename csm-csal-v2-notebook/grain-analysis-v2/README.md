# CSM / CSAL grain analysis V2

Paste the six cells into a new personal Databricks notebook in filename order and run them from top to bottom.

The notebook is read-only. It profiles the existing personal POC objects and creates three presentation charts:

1. Rows retained at each business grain
2. Repeated physical rows at the stated grain
3. Agent-facing columns, accuracy and response time

The existing `09-sales-ai-v2-master-poc` and `09-sales-ai-v2-benchmark` notebooks remain unchanged as technical evidence.

Important: grain is a row meaning, not a quantity. The booking path removes repeated physical rows at booking scope. The commitment fact is smaller because it stores a different business scope once. The allocation fact intentionally keeps detailed allocation slices.
