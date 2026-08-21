# Simulator until Razorpay Test Mode keys exist

We have an LLM key, not Razorpay Test Mode keys. Execution still goes through a tool seam. The adapter behind that seam is a labelled Simulator. When Test Mode keys exist, swap the adapter. Do not pretend Simulator calls are Razorpay.

Money-moving actions stay behind the policy gate either way.

**Status:** accepted
