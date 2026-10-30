import pathlib

symbols_file = pathlib.Path('/home/paras/.darling/all_truly_missing.txt')
if not symbols_file.exists():
    raise FileNotFoundError("Missing /home/paras/.darling/all_truly_missing.txt")

with open(symbols_file, 'r', encoding='utf-8') as f:
    raw_symbols = sorted(list(set(line.strip() for line in f if line.strip())))

# Also ensure truly_missing_arccore symbols are included if any were separate
arc_file = pathlib.Path('/home/paras/.darling/truly_missing_arccore.txt')
if arc_file.exists():
    with open(arc_file, 'r', encoding='utf-8') as f:
        raw_symbols.extend([line.strip() for line in f if line.strip()])

symbols = sorted(list(set(raw_symbols)))

objc_classes = set()
objc_ehtypes = set()
constants = set()
swift_data = set()
functions = set()

# Special symbols provided directly in the shim C header
builtin_header_symbols = {
    '___NSArray0__struct',
    '___NSDictionary0__struct',
    '___atomic_load',
    '___atomic_store',
    '___atomic_compare_exchange'
}

known_constants = {
    'CADynamicRangeHigh', 'CADynamicRangeStandard',
    'kCGDisplayStreamColorSpace', 'kCGDisplayStreamDestinationRect',
    'kCGDisplayStreamMinimumFrameTime', 'kCGDisplayStreamPreserveAspectRatio',
    'kCGColorSpaceExtendedLinearITUR_2020', 'kCGColorSpaceITUR_2100_HLG', 'kCGColorSpaceITUR_2100_PQ',
    'MTLCommonCounterSetTimestamp', 'MTLCommonCounterTimestamp',
    'MTLDeviceRemovalRequestedNotification', 'MTLDeviceWasRemovedNotification',
    'NSURLContentTypeKey', 'UNNotificationDefaultActionIdentifier',
    'UNNotificationDismissActionIdentifier'
}

swift_data_suffixes = (
    'VMn', 'OMn', 'CMn', 'AMc', 'AWP', 'WP', 'WG', 'WV',
    'Mp', 'MF', 'Mr', 'TN', 'TM', 'N'
)

for s in symbols:
    if s in builtin_header_symbols:
        continue

    if s.startswith('_OBJC_CLASS_$_'):
        cname = s[len('_OBJC_CLASS_$_'):]
        objc_classes.add(cname)
    elif s.startswith('_OBJC_METACLASS_$_'):
        cname = s[len('_OBJC_METACLASS_$_'):]
        objc_classes.add(cname)
    elif s.startswith('_OBJC_EHTYPE_$_'):
        objc_ehtypes.add(s)
    elif s.startswith('_$'):
        # Swift symbol
        if any(s.endswith(suf) for suf in swift_data_suffixes):
            swift_data.add(s)
        else:
            functions.add(s)
    else:
        # C symbol
        clean_name = s.lstrip('_')
        if clean_name in known_constants or clean_name.startswith('k') or any(kw in clean_name for kw in (
            'Domain', 'Notification', 'Attribute', 'Key', 'Type', 'Kind',
            'Preference', 'Identifier', 'Subrole', 'Rate', 'Limit', 'Protocol'
        )):
            constants.add(s)
        else:
            functions.add(s)

print(f'ObjC Classes: {len(objc_classes)}')
print(f'ObjC EHTypes: {len(objc_ehtypes)}')
print(f'Constants: {len(constants)}')
print(f'Swift Data: {len(swift_data)}')
print(f'Functions: {len(functions)}')
print(f'Total shim symbols: {len(objc_classes) + len(objc_ehtypes) + len(constants) + len(swift_data) + len(functions)}')

out = []
out.append('''/*
 * Unified Tahoe 16 Complete Compatibility Shim for Darling
 * Auto-generated to cover all missing modern macOS 13-16 symbols.
 */

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

typedef struct objc_class *Class;
typedef struct objc_object *id;
typedef struct objc_selector *SEL;
typedef id (*IMP)(id, SEL, ...);
typedef signed char BOOL;
#define YES ((BOOL)1)
#define NO ((BOOL)0)
#define nil ((id)0)

extern BOOL class_addMethod(Class cls, SEL name, IMP imp, const char *types);
extern Class object_getClass(id obj);

static id tahoe_generic_stub(id self, SEL _cmd, ...) {
    return (id)0;
}

@interface NSObject
@end

@interface TahoeStubBase : NSObject
@end

@implementation TahoeStubBase
+ (BOOL)resolveInstanceMethod:(SEL)sel {
    class_addMethod((Class)self, sel, (IMP)tahoe_generic_stub, "@@:@");
    return YES;
}
+ (BOOL)resolveClassMethod:(SEL)sel {
    Class meta = object_getClass((id)self);
    class_addMethod(meta, sel, (IMP)tahoe_generic_stub, "@@:@");
    return YES;
}
@end

// Empty array and dictionary singletons
const uint64_t __NSArray0__struct[4] = {0, 0, 0, 0};
const uint64_t __NSDictionary0__struct[4] = {0, 0, 0, 0};

// Atomic built-in functions via asm symbol binding
void my_atomic_store(size_t size, void *ptr, void *val, int memorder) __asm__("___atomic_store");
void my_atomic_store(size_t size, void *ptr, void *val, int memorder) {
    if (size == 1) *(uint8_t*)ptr = *(uint8_t*)val;
    else if (size == 2) *(uint16_t*)ptr = *(uint16_t*)val;
    else if (size == 4) *(uint32_t*)ptr = *(uint32_t*)val;
    else if (size == 8) *(uint64_t*)ptr = *(uint64_t*)val;
    else __builtin_memcpy(ptr, val, size);
}

void my_atomic_load(size_t size, const void *ptr, void *val, int memorder) __asm__("___atomic_load");
void my_atomic_load(size_t size, const void *ptr, void *val, int memorder) {
    if (size == 1) *(uint8_t*)val = *(const uint8_t*)ptr;
    else if (size == 2) *(uint16_t*)val = *(const uint16_t*)ptr;
    else if (size == 4) *(uint32_t*)val = *(const uint32_t*)ptr;
    else if (size == 8) *(uint64_t*)val = *(const uint64_t*)ptr;
    else __builtin_memcpy(val, ptr, size);
}

bool my_atomic_compare_exchange(size_t size, void *ptr, void *expected, void *desired, int success_order, int failure_order) __asm__("___atomic_compare_exchange");
bool my_atomic_compare_exchange(size_t size, void *ptr, void *expected, void *desired, int success_order, int failure_order) {
    if (__builtin_memcmp(ptr, expected, size) == 0) {
        __builtin_memcpy(ptr, desired, size);
        return true;
    } else {
        __builtin_memcpy(expected, ptr, size);
        return false;
    }
}
''')

out.append('// Objective-C Classes')
for c in sorted(objc_classes):
    out.append(f'@interface {c} : TahoeStubBase @end\n@implementation {c} @end\n')

out.append('// Objective-C Exception Handling Types')
for idx, eh in enumerate(sorted(objc_ehtypes)):
    safe_id = f"objc_eh_{idx:05d}"
    out.append(f'const void* {safe_id} __asm__("{eh}") = (void*)0;')

out.append('\n// Constants & Strings')
for idx, c in enumerate(sorted(constants)):
    safe_id = f"const_{idx:05d}"
    clean_val = c.replace('"', '\\"')
    out.append(f'const char* {safe_id} __asm__("{c}") = "{clean_val}";')

out.append('\n// Swift Data Descriptors (Zeroed Memory)')
for idx, d in enumerate(sorted(swift_data)):
    safe_id = f"data_{idx:05d}"
    out.append(f'const uint64_t {safe_id}[16] __asm__("{d}") = {{0}};')

out.append('\n// Functions (Returns 0 / NULL)')
for idx, fn in enumerate(sorted(functions)):
    safe_id = f"fn_{idx:05d}"
    out.append(f'void* {safe_id}(void) __asm__("{fn}");')
    out.append(f'void* {safe_id}(void) {{ return (void*)0; }}')

content = '\n'.join(out)
out_path = pathlib.Path('/home/paras/.darling/usr/lib/tahoe_shim_full.m')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Wrote {out_path} ({len(content)} bytes)')
