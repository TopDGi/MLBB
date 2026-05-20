import json
from collections import Counter

with open('lipstick_db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

issues = {
    'null_bgr': [],
    'invalid_bgr_type': [],
    'invalid_bgr_range': [],
    'missing_tone': [],
}

for i, item in enumerate(db):
    name = item.get('name', f'Unknown #{i}')

    # Check BGR
    bgr = item.get('bgr')
    if bgr is None:
        issues['null_bgr'].append((i, name))
    elif not isinstance(bgr, list) or len(bgr) != 3:
        issues['invalid_bgr_type'].append((i, name, bgr))
    else:
        try:
            if not all(isinstance(x, (int, float)) for x in bgr) or not all(0 <= x <= 255 for x in bgr):
                issues['invalid_bgr_range'].append((i, name, bgr))
        except:
            issues['invalid_bgr_type'].append((i, name, bgr))

    # Check tone
    if not item.get('tone'):
        issues['missing_tone'].append((i, name))

print(f"Total items: {len(db)}\n")
print(f"[NULL BGR] {len(issues['null_bgr'])}")
if issues['null_bgr']:
    for idx, name in issues['null_bgr'][:10]:
        print(f"  [{idx}] {name}")

print(f"\n[INVALID TYPE] {len(issues['invalid_bgr_type'])}")
if issues['invalid_bgr_type']:
    for idx, name, bgr in issues['invalid_bgr_type'][:10]:
        print(f"  [{idx}] {name} -> {bgr}")

print(f"\n[OUT OF RANGE] {len(issues['invalid_bgr_range'])}")
if issues['invalid_bgr_range']:
    for idx, name, bgr in issues['invalid_bgr_range'][:10]:
        print(f"  [{idx}] {name} -> {bgr}")

print(f"\n[NO TONE] {len(issues['missing_tone'])}")
if issues['missing_tone']:
    for idx, name in issues['missing_tone'][:10]:
        print(f"  [{idx}] {name}")

total_bad = sum(len(v) for v in issues.values())
print(f"\nTOTAL PROBLEMS: {total_bad}/{len(db)} ({100*total_bad/len(db):.1f}%)")
