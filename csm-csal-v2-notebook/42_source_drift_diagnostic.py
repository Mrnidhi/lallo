# Metadata-only check. It does not read customer rows or send an agent question.

live = source_markers()
changes = []

for name, saved in MANIFEST["sources"]["tables"].items():
    current = live["tables"][name]
    if current != saved:
        changes.append(
            {
                "source": name,
                "saved_version": saved["version"],
                "current_version": current["version"],
                "same_table_id": saved["id"] == current["id"],
                "same_schema": saved["schema_sha256"] == current["schema_sha256"],
            }
        )

print("Changed source metadata:")
if changes:
    for change in changes:
        print(change)
else:
    print("None")

view_changed = (
    live["booking_view_sha256"]
    != MANIFEST["sources"]["booking_view_sha256"]
)
print("Booking view definition changed:", view_changed)
