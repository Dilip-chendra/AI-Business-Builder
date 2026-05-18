import os
p = os.path.join("frontend", "app", "marketing", "page.tsx")
content = open(p, encoding="utf-8").read()
return_start = content.find("  return (")
engine_tab = content.find("{/* ENGINE TAB */")
new_opening = "  return (\n    <div>\n\n      "
new_content = content[:return_start] + new_opening + content[engine_tab:]
open(p, "w", encoding="utf-8").write(new_content)
print("Done. Lines:", new_content.count("\n"))
