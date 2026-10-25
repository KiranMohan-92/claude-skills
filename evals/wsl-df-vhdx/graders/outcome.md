---
type: llm
weight: 1
---

PASS only if the answer says no (or not necessarily): WSL's disk is a .vhdx file stored on a Windows drive (C: by default), df shows the virtual disk's size rather than physical free space, and writing inside WSL still consumes space on the drive holding the .vhdx, so check that drive's real free space first.
