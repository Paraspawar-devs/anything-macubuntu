import pathlib

symbols_file = pathlib.Path('/home/paras/.darling/all_truly_missing.txt')
if not symbols_file.exists():
    raise FileNotFoundError("Missing /home/paras/.darling/all_truly_missing.txt")

with open(symbols_file, 'r', encoding='utf-8') as f:
    raw_symbols = sorted(list(set(line.strip() for line in f if line.strip())))

arc_file = pathlib.Path('/home/paras/.darling/truly_missing_arccore.txt')
if arc_file.exists():
    with open(arc_file, 'r', encoding='utf-8') as f:
        raw_symbols.extend([line.strip() for line in f if line.strip()])

unres_file = pathlib.Path('/home/paras/.darling/arc_unresolved_symbols.txt')
if unres_file.exists():
    with open(unres_file, 'r', encoding='utf-8') as f:
        raw_symbols.extend([line.strip() for line in f if line.strip()])

vscode_file = pathlib.Path('/home/paras/.darling/vscode_missing_symbols.txt')
if vscode_file.exists():
    with open(vscode_file, 'r', encoding='utf-8') as f:
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
    '___atomic_compare_exchange',
    '_sandbox_init_with_parameters',
    '_sandbox_check',
    '_sandbox_free_error',
    '_CCRandomGenerateBytes',
    '_CC_SHA256',
    '_CC_SHA1',
    '_CC_MD5',
    '_CC_SHA1_Init',
    '_CC_SHA1_Update',
    '_CC_SHA1_Final',
    '___swift_FORCE_LOAD_$_swiftCoreData',
    '_copyfile',
    '___dirhelper',
    '_swift_once',
    '_swift_allocObject',
    '_swift_retain',
    '_swift_release',
    '_swift_retain_n',
    '_swift_release_n',
    '_swift_bridgeObjectRetain',
    '_swift_bridgeObjectRelease',
    '_swift_bridgeObjectRetain_n',
    '_swift_bridgeObjectRelease_n',
    '_swift_beginAccess',
    '_swift_endAccess',
    '_swift_projectBox',
    '_swift_deallocBox',
    '_swift_deallocObject',
    '_swift_deallocClassInstance',
    '_$ss27_stringCompareWithSmolCheck__9expectingSbs11_StringGutsV_ADs01_G16ComparisonResultOtF',
    '_$sSysE2eeoiySbx_qd__tSyRd__lFZ',
    '_$ss11CommandLineO9argumentsSaySSGvgZ',
    '_$sSS11utf8CStrings15ContiguousArrayVys4Int8VGvg',
    '_swift_slowAlloc',
    '_swift_slowDealloc',
    '_swift_isUniquelyReferenced_native',
    '_swift_isUniquelyReferenced_nonNull_native',
    '_swift_isUniquelyReferencedNonObjC_nonNull',
    '_swift_isUniquelyReferencedNonObjC_nonNull_bridgeObject',
    '_swift_unknownObjectRetain',
    '_swift_unknownObjectRelease',
    '_swift_unknownObjectRetain_n',
    '_swift_unknownObjectRelease_n',
    '_swift_unownedRetain',
    '_swift_unownedRelease',
    '_swift_unownedRetainStrong',
    '_swift_unownedRetainStrongAndRelease',
    '_swift_nonatomic_unownedRetainStrong',
    '_swift_nonatomic_unownedRetainStrongAndRelease',
    '_swift_unownedCheck',
    '_swift_unknownObjectUnownedInit',
    '_swift_unknownObjectUnownedAssign',
    '_swift_unknownObjectUnownedLoadStrong',
    '_swift_unknownObjectUnownedDestroy',
    '_swift_unknownObjectWeakInit',
    '_swift_unknownObjectWeakAssign',
    '_swift_unknownObjectWeakLoadStrong',
    '_swift_unknownObjectWeakDestroy',
    '_swift_weakInit',
    '_swift_weakAssign',
    '_swift_weakLoadStrong',
    '_swift_weakDestroy',
    '_swift_weakCopyInit',
    '_swift_weakTakeInit',
    '_swift_weakCopyAssign',
    '_swift_weakTakeAssign',
    '_swift_getObjectType',
    '_swift_initStackObject',
    '_swift_initStaticObject',
    '_swift_setDeallocating',
    '_swift_getExistentialTypeMetadata',
    '_swift_getGenericMetadata',
    '_swift_getTypeByMangledNameInContext',
    '_swift_getTypeByMangledNameInContextInMetadataState',
    '_swift_dynamicCastObjCProtocolConditional',
    '_swift_conformsToProtocol',
    '_$sSS10FoundationE36_unconditionallyBridgeFromObjectiveCySSSo8NSStringCSgFZ',
    '_$sSS12_cocoaStringSSyXl_tcfC',
    '_$sSS10FoundationE19_bridgeToObjectiveCSo8NSStringCyF',
    '_swift_getObjCClassFromMetadata',
    '_swift_getObjCClassMetadata',
    '_$s10Foundation3URLVMa',
    '_$sSD10FoundationE36_unconditionallyBridgeFromObjectiveCySDyxq_GSo12NSDictionaryCSgFZ',
    '_$sSh10FoundationE36_unconditionallyBridgeFromObjectiveCyShyxGSo5NSSetCSgFZ',
    '_$sSa10FoundationE36_unconditionallyBridgeFromObjectiveCySayxGSo7NSArrayCSgFZ',
    '_$s10Foundation3URLV17lastPathComponentSSvg',
    '_$s10Foundation3URLV13pathExtensionSSvg',
    '_$s10Foundation3URLV4pathSSvg',
    '_swift_getSingletonMetadata',
    '_swift_getMetatypeMetadata',
    '_swift_getExistentialMetatypeMetadata',
    '_swift_getOpaqueTypeMetadata',
    '_swift_getWitnessTable',
    '_swift_getAssociatedTypeWitness',
    '_swift_getAssociatedConformanceWitness',
    '_swift_getObjCClassFromObject',
    '_swift_initClassMetadata',
    '_swift_updateClassMetadata'
}

known_constants = {
    'CADynamicRangeHigh', 'CADynamicRangeStandard',
    'kCGDisplayStreamColorSpace', 'kCGDisplayStreamDestinationRect',
    'kCGDisplayStreamMinimumFrameTime', 'kCGDisplayStreamPreserveAspectRatio',
    'kCGColorSpaceExtendedLinearITUR_2020', 'kCGColorSpaceITUR_2100_HLG', 'kCGColorSpaceITUR_2100_PQ',
    'MTLCommonCounterSetTimestamp', 'MTLCommonCounterTimestamp',
    'MTLDeviceRemovalRequestedNotification', 'MTLDeviceWasRemovedNotification',
    'NSURLContentTypeKey', 'UNNotificationDefaultActionIdentifier',
    'UNNotificationDismissActionIdentifier',
    'kLSQuarantineDataURLKey', 'kLSQuarantineOriginURLKey', 'kLSQuarantineTypeKey',
    'kLSQuarantineTypeOtherDownload', 'kLSQuarantineTypeWebDownload',
    'kLSSharedFileListItemLast', 'kLSSharedFileListLoginItemHidden',
    'kLSSharedFileListSessionLoginItems', 'kMDItemWhereFroms',
    'kODAttributeTypeAllAttributes', 'kODAttributeTypeAltSecurityIdentities',
    'kODAttributeTypeMetaRecordName', 'kTISPropertyInputSourceID',
    'kTISPropertyUnicodeKeyLayoutData', 'kUTTagClassFilenameExtension',
    'kUTTagClassMIMEType', 'kUTTypeImage', 'APP_SANDBOX_READ', 'APP_SANDBOX_READ_WRITE'
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
        if any(s.endswith(suf) for suf in swift_data_suffixes):
            swift_data.add(s)
        else:
            functions.add(s)
    else:
        clean_name = s.lstrip('_')
        is_func = False
        if clean_name.startswith('swift_') or s.startswith('___swift_'):
            is_func = True
        elif any(v in clean_name for v in (
            'Copy', 'Get', 'Set', 'Create', 'Add', 'Remove', 'Register', 'Unregister',
            'Translate', 'Transform', 'Conforms', 'Is', 'Init', 'Delete', 'Destroy',
            'Alloc', 'Release', 'Retain', 'Check', 'Lookup', 'Update', 'Final',
            'Perform', 'Show', 'Hide', 'Enable', 'Disable', 'Start', 'Stop', 'Pause', 'Resume',
            'Open', 'Close', 'Read', 'Write', 'Send', 'Receive', 'Load', 'Unload', 'Run', 'Handle'
        )):
            is_func = True

        if is_func:
            functions.add(s)
        elif clean_name in known_constants or clean_name.startswith('k') or any(kw in clean_name for kw in (
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
print(f'Total shim symbols: {len(objc_classes) + len(objc_ehtypes) + len(constants) + len(swift_data) + len(functions) + len(builtin_header_symbols)}')

out = []
out.append('''/*
 * Unified Tahoe 16 Complete Compatibility Shim for AnythingMac
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

extern int sched_yield(void);
extern void *malloc(size_t);
extern void free(void*);
extern void *memset(void*, int, size_t);
extern size_t strlen(const char*);
extern SEL sel_registerName(const char *name);
extern Class objc_getClass(const char *name);
extern id objc_msgSend(id self, SEL op, ...);

extern BOOL class_addMethod(Class cls, SEL name, IMP imp, const char *types);
extern Class object_getClass(id obj);
extern BOOL class_respondsToSelector(Class cls, SEL sel);

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

// Swift overlay force-load dummy symbols
const void* __swift_force_load_coredata __asm__("___swift_FORCE_LOAD_$_swiftCoreData") = (void*)0;

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

// Sandbox API implementations
int my_sandbox_init(const char *profile, uint64_t flags, const char **params, char **errorbuf) __asm__("_sandbox_init_with_parameters");
int my_sandbox_init(const char *profile, uint64_t flags, const char **params, char **errorbuf) {
    if (errorbuf) *errorbuf = (char*)0;
    return 0; // Success
}

int my_sandbox_check(int pid, const char *operation, int type, ...) __asm__("_sandbox_check");
int my_sandbox_check(int pid, const char *operation, int type, ...) {
    return 0; // Allowed
}

void my_sandbox_free_error(char *errorbuf) __asm__("_sandbox_free_error");
void my_sandbox_free_error(char *errorbuf) {}

// Crypto API implementations
int my_cc_random(void *bytes, size_t count) __asm__("_CCRandomGenerateBytes");
int my_cc_random(void *bytes, size_t count) {
    for (size_t i = 0; i < count; i++) {
        ((uint8_t*)bytes)[i] = (uint8_t)(i * 37 + 13);
    }
    return 0;
}

unsigned char *my_cc_sha256(const void *data, uint32_t len, unsigned char *md) __asm__("_CC_SHA256");
unsigned char *my_cc_sha256(const void *data, uint32_t len, unsigned char *md) {
    static unsigned char static_buf[32];
    unsigned char *out = md ? md : static_buf;
    __builtin_memset(out, 0xaa, 32);
    return out;
}

unsigned char *my_cc_sha1(const void *data, uint32_t len, unsigned char *md) __asm__("_CC_SHA1");
unsigned char *my_cc_sha1(const void *data, uint32_t len, unsigned char *md) {
    static unsigned char static_buf[20];
    unsigned char *out = md ? md : static_buf;
    __builtin_memset(out, 0xbb, 20);
    return out;
}

unsigned char *my_cc_md5(const void *data, uint32_t len, unsigned char *md) __asm__("_CC_MD5");
unsigned char *my_cc_md5(const void *data, uint32_t len, unsigned char *md) {
    static unsigned char static_buf[16];
    unsigned char *out = md ? md : static_buf;
    __builtin_memset(out, 0xcc, 16);
    return out;
}

int my_cc_sha1_init(void *c) __asm__("_CC_SHA1_Init");
int my_cc_sha1_init(void *c) { return 1; }
int my_cc_sha1_update(void *c, const void *data, uint32_t len) __asm__("_CC_SHA1_Update");
int my_cc_sha1_update(void *c, const void *data, uint32_t len) { return 1; }
int my_cc_sha1_final(unsigned char *md, void *c) __asm__("_CC_SHA1_Final");
int my_cc_sha1_final(unsigned char *md, void *c) {
    if (md) __builtin_memset(md, 0xbb, 20);
    return 1;
}

// Swift runtime core implementations
void my_swift_once(uintptr_t *predicate, void (*fn)(void *), void *context) __asm__("_swift_once");
void my_swift_once(uintptr_t *predicate, void (*fn)(void *), void *context) {
    if (!predicate || !fn) return;
    if (__atomic_load_n(predicate, __ATOMIC_ACQUIRE) == (uintptr_t)-1) {
        return;
    }
    uintptr_t expected = 0;
    if (__atomic_compare_exchange_n(predicate, &expected, 1, false, __ATOMIC_SEQ_CST, __ATOMIC_SEQ_CST)) {
        fn(context);
        __atomic_store_n(predicate, (uintptr_t)-1, __ATOMIC_RELEASE);
    } else {
        while (__atomic_load_n(predicate, __ATOMIC_ACQUIRE) != (uintptr_t)-1) {
            sched_yield();
        }
    }
}

void *my_swift_allocObject(void *metadata, size_t requiredSize, size_t requiredAlignmentMask) __asm__("_swift_allocObject");
void *my_swift_allocObject(void *metadata, size_t requiredSize, size_t requiredAlignmentMask) {
    if (requiredSize < 32) requiredSize = 32;
    void *ptr = malloc(requiredSize);
    if (ptr) {
        memset(ptr, 0, requiredSize);
        *(void**)ptr = metadata;
        uint32_t *ref = (uint32_t*)((char*)ptr + sizeof(void*));
        ref[0] = 1;
        ref[1] = 1;
    }
    return ptr;
}

void *my_swift_retain(void *object) __asm__("_swift_retain");
void *my_swift_retain(void *object) {
    if (object) {
        uint32_t *ref = (uint32_t*)((char*)object + sizeof(void*));
        __atomic_add_fetch(ref, 1, __ATOMIC_RELAXED);
    }
    return object;
}

void my_swift_release(void *object) __asm__("_swift_release");
void my_swift_release(void *object) {
    if (object) {
        uint32_t *ref = (uint32_t*)((char*)object + sizeof(void*));
        __atomic_sub_fetch(ref, 1, __ATOMIC_RELEASE);
    }
}

void *my_swift_bridgeObjectRetain(void *object) __asm__("_swift_bridgeObjectRetain");
void *my_swift_bridgeObjectRetain(void *object) {
    return object;
}

void my_swift_bridgeObjectRelease(void *object) __asm__("_swift_bridgeObjectRelease");
void my_swift_bridgeObjectRelease(void *object) {}

void *my_swift_retain_n(void *object, uint32_t n) __asm__("_swift_retain_n");
void *my_swift_retain_n(void *object, uint32_t n) {
    if (object) {
        uint32_t *ref = (uint32_t*)((char*)object + sizeof(void*));
        __atomic_add_fetch(ref, n, __ATOMIC_RELAXED);
    }
    return object;
}

void my_swift_release_n(void *object, uint32_t n) __asm__("_swift_release_n");
void my_swift_release_n(void *object, uint32_t n) {
    if (object) {
        uint32_t *ref = (uint32_t*)((char*)object + sizeof(void*));
        __atomic_sub_fetch(ref, n, __ATOMIC_RELEASE);
    }
}

void *my_swift_bridgeObjectRetain_n(void *object, uint32_t n) __asm__("_swift_bridgeObjectRetain_n");
void *my_swift_bridgeObjectRetain_n(void *object, uint32_t n) {
    return object;
}

void my_swift_bridgeObjectRelease_n(void *object, uint32_t n) __asm__("_swift_bridgeObjectRelease_n");
void my_swift_bridgeObjectRelease_n(void *object, uint32_t n) {}

void my_swift_beginAccess(void *pointer, void *buffer, uintptr_t flags, void *pc) __asm__("_swift_beginAccess");
void my_swift_beginAccess(void *pointer, void *buffer, uintptr_t flags, void *pc) {}

void my_swift_endAccess(void *buffer) __asm__("_swift_endAccess");
void my_swift_endAccess(void *buffer) {}

void *my_swift_projectBox(void *box) __asm__("_swift_projectBox");
void *my_swift_projectBox(void *box) {
    return box ? (void*)((char*)box + 16) : (void*)0;
}

void my_swift_deallocBox(void *box) __asm__("_swift_deallocBox");
void my_swift_deallocBox(void *box) {}

void my_swift_deallocObject(void *object, size_t size, size_t align) __asm__("_swift_deallocObject");
void my_swift_deallocObject(void *object, size_t size, size_t align) {
    if (object) free(object);
}

void my_swift_deallocClassInstance(void *object, size_t size, size_t align) __asm__("_swift_deallocClassInstance");
void my_swift_deallocClassInstance(void *object, size_t size, size_t align) {
    if (object) free(object);
}

// Swift String & Comparison helpers
struct SwiftStringView {
    const uint8_t *data;
    size_t len;
    uint8_t inline_buf[16];
};

static inline struct SwiftStringView decode_swift_string(uint64_t w0, uint64_t w1) {
    struct SwiftStringView view;
    // Small string: bit 61 is set
    if ((w1 & 0x2000000000000000ULL) != 0) {
        size_t count = (w1 >> 56) & 0x0f;
        if (count > 15) count = 15;
        view.len = count;
        __builtin_memcpy(&view.inline_buf[0], &w0, 8);
        __builtin_memcpy(&view.inline_buf[8], &w1, 7);
        view.data = view.inline_buf;
    } else {
        size_t count = w0 & 0x0000ffffffffffffULL;
        uintptr_t addr = (w1 & 0x0000ffffffffffffULL) + 32;
        view.len = count;
        view.data = (const uint8_t*)addr;
    }
    return view;
}

bool my_string_compare_smol(uint64_t lhs0, uint64_t lhs1, uint64_t rhs0, uint64_t rhs1, int expecting)
    __asm__("_$ss27_stringCompareWithSmolCheck__9expectingSbs11_StringGutsV_ADs01_G16ComparisonResultOtF");
bool my_string_compare_smol(uint64_t lhs0, uint64_t lhs1, uint64_t rhs0, uint64_t rhs1, int expecting) {
    if (lhs0 == rhs0 && lhs1 == rhs1) {
        return (expecting == 0);
    }
    struct SwiftStringView l = decode_swift_string(lhs0, lhs1);
    struct SwiftStringView r = decode_swift_string(rhs0, rhs1);
    if (!l.data || !r.data) {
        return false;
    }
    size_t min_len = l.len < r.len ? l.len : r.len;
    int cmp = __builtin_memcmp(l.data, r.data, min_len);
    if (cmp == 0) {
        if (l.len == r.len) cmp = 0;
        else cmp = (l.len < r.len) ? -1 : 1;
    }
    if (expecting == 0) {
        return (cmp == 0);
    } else {
        return (cmp < 0);
    }
}

bool my_string_protocol_eq(uint64_t lhs0, uint64_t lhs1, uint64_t rhs0, uint64_t rhs1, void *wt)
    __asm__("_$sSysE2eeoiySbx_qd__tSyRd__lFZ");
bool my_string_protocol_eq(uint64_t lhs0, uint64_t lhs1, uint64_t rhs0, uint64_t rhs1, void *wt) {
    return my_string_compare_smol(lhs0, lhs1, rhs0, rhs1, 0);
}

struct SwiftStringPair {
    uint64_t w0;
    uint64_t w1;
};

static inline struct SwiftStringPair make_swift_string(const char *str, size_t len) {
    struct SwiftStringPair res = {0, 0xE000000000000000ULL};
    if (!str || len == 0) return res;
    if (len <= 15) {
        uint64_t w0 = 0, w1 = 0;
        if (len <= 8) {
            __builtin_memcpy(&w0, str, len);
        } else {
            __builtin_memcpy(&w0, str, 8);
            __builtin_memcpy(&w1, str + 8, len - 8);
        }
        w1 |= ((uint64_t)(0xE0 | len) << 56);
        res.w0 = w0;
        res.w1 = w1;
        return res;
    } else {
        size_t alloc_sz = 32 + len + 16;
        char *buf = (char*)malloc(alloc_sz);
        if (buf) {
            memset(buf, 0, alloc_sz);
            *(uint64_t*)(buf + 8) = 2; // refcount
            *(uint64_t*)(buf + 16) = len; // count
            *(uint64_t*)(buf + 24) = len + 16; // capacity
            __builtin_memcpy(buf + 32, str, len);
            buf[32 + len] = 0;
            res.w0 = (uint64_t)len;
            res.w1 = (uintptr_t)buf;
        }
        return res;
    }
}

static inline const char* get_nsstring_utf8(void *obj, size_t *out_len) {
    if (!obj) {
        if (out_len) *out_len = 0;
        return "";
    }
    const char *ptr = *(const char**)((char*)obj + 16);
    size_t len = *(size_t*)((char*)obj + 24);
    if (ptr && (uintptr_t)ptr > 0x10000 && len < 1000000) {
        if (out_len) *out_len = len;
        return ptr;
    }
    SEL utf8_sel = sel_registerName("UTF8String");
    if (utf8_sel && class_respondsToSelector(object_getClass((id)obj), utf8_sel)) {
        const char *s = (const char*)objc_msgSend((id)obj, utf8_sel);
        if (s) {
            if (out_len) *out_len = strlen(s);
            return s;
        }
    }
    if (out_len) *out_len = 0;
    return "";
}

struct SwiftStringPair my_string_unconditionallyBridge(void *nsstring)
    __asm__("_$sSS10FoundationE36_unconditionallyBridgeFromObjectiveCySSSo8NSStringCSgFZ");
struct SwiftStringPair my_string_unconditionallyBridge(void *nsstring) {
    size_t len = 0;
    const char *str = get_nsstring_utf8(nsstring, &len);
    return make_swift_string(str, len);
}

struct SwiftStringPair my_string_cocoaString(void *nsstring)
    __asm__("_$sSS12_cocoaStringSSyXl_tcfC");
struct SwiftStringPair my_string_cocoaString(void *nsstring) {
    return my_string_unconditionallyBridge(nsstring);
}

id my_string_bridgeToObjectiveC(uint64_t w0, uint64_t w1)
    __asm__("_$sSS10FoundationE19_bridgeToObjectiveCSo8NSStringCyF");
id my_string_bridgeToObjectiveC(uint64_t w0, uint64_t w1) {
    struct SwiftStringView view = decode_swift_string(w0, w1);
    Class nsstr_cls = objc_getClass("NSString");
    if (nsstr_cls && view.data) {
        SEL alloc_sel = sel_registerName("alloc");
        SEL init_sel = sel_registerName("initWithBytes:length:encoding:");
        if (alloc_sel && init_sel) {
            id inst = objc_msgSend((id)nsstr_cls, alloc_sel);
            return objc_msgSend(inst, init_sel, view.data, view.len, 4 /* NSUTF8StringEncoding */);
        }
    }
    return (id)0;
}

// Swift CommandLine.arguments & String.utf8CString implementations
static const uint64_t my_empty_swift_array[8] = {
    0,                      // metadata pointer
    0x8000000000000002ULL,  // immortal refcount
    0,                      // count = 0
    0,                      // capacity = 0
    0, 0, 0, 0
};

static const uint64_t my_empty_swift_dictionary[8] = {
    0,                      // metadata pointer
    0x8000000000000002ULL,  // immortal refcount
    0,                      // count = 0
    0,                      // capacity = 0
    0, 0, 0, 0
};

void *my_commandline_arguments(void) __asm__("_$ss11CommandLineO9argumentsSaySSGvgZ");
void *my_commandline_arguments(void) {
    return (void*)my_empty_swift_array;
}

void *my_dictionary_unconditionallyBridge(void *nsdict)
    __asm__("_$sSD10FoundationE36_unconditionallyBridgeFromObjectiveCySDyxq_GSo12NSDictionaryCSgFZ");
void *my_dictionary_unconditionallyBridge(void *nsdict) {
    return (void*)my_empty_swift_dictionary;
}

void *my_set_unconditionallyBridge(void *nsset)
    __asm__("_$sSh10FoundationE36_unconditionallyBridgeFromObjectiveCyShyxGSo5NSSetCSgFZ");
void *my_set_unconditionallyBridge(void *nsset) {
    return (void*)my_empty_swift_array;
}

void *my_array_unconditionallyBridge(void *nsarray)
    __asm__("_$sSa10FoundationE36_unconditionallyBridgeFromObjectiveCySayxGSo7NSArrayCSgFZ");
void *my_array_unconditionallyBridge(void *nsarray) {
    return (void*)my_empty_swift_array;
}

void *my_string_utf8cstring(uint64_t w0, uint64_t w1)
    __asm__("_$sSS11utf8CStrings15ContiguousArrayVys4Int8VGvg");
void *my_string_utf8cstring(uint64_t w0, uint64_t w1) {
    struct SwiftStringView view = decode_swift_string(w0, w1);
    size_t alloc_size = 0x20 + view.len + 16;
    char *buf = (char*)malloc(alloc_size);
    if (!buf) return (void*)0;
    memset(buf, 0, alloc_size);
    *(uint64_t*)(buf + 0x08) = 2; // refcount
    *(uint64_t*)(buf + 0x10) = view.len + 1; // count
    *(uint64_t*)(buf + 0x18) = view.len + 16; // capacity
    if (view.data && view.len > 0) {
        __builtin_memcpy(buf + 0x20, view.data, view.len);
    }
    buf[0x20 + view.len] = 0;
    return (void*)buf;
}

void *my_swift_slowAlloc(size_t bytes, size_t alignMask) __asm__("_swift_slowAlloc");
void *my_swift_slowAlloc(size_t bytes, size_t alignMask) { return malloc(bytes); }

void my_swift_slowDealloc(void *ptr, size_t bytes, size_t alignMask) __asm__("_swift_slowDealloc");
void my_swift_slowDealloc(void *ptr, size_t bytes, size_t alignMask) { if (ptr) free(ptr); }

bool my_swift_isUniquelyReferenced_native(const void *ptr) __asm__("_swift_isUniquelyReferenced_native");
bool my_swift_isUniquelyReferenced_native(const void *ptr) { return true; }

bool my_swift_isUniquelyReferenced_nonNull_native(const void *ptr) __asm__("_swift_isUniquelyReferenced_nonNull_native");
bool my_swift_isUniquelyReferenced_nonNull_native(const void *ptr) { return true; }

bool my_swift_isUniquelyReferencedNonObjC_nonNull(const void *ptr) __asm__("_swift_isUniquelyReferencedNonObjC_nonNull");
bool my_swift_isUniquelyReferencedNonObjC_nonNull(const void *ptr) { return true; }

bool my_swift_isUniquelyReferencedNonObjC_nonNull_bridgeObject(uintptr_t bits) __asm__("_swift_isUniquelyReferencedNonObjC_nonNull_bridgeObject");
bool my_swift_isUniquelyReferencedNonObjC_nonNull_bridgeObject(uintptr_t bits) { return true; }

void *my_swift_unknownObjectRetain(void *obj) __asm__("_swift_unknownObjectRetain");
void *my_swift_unknownObjectRetain(void *obj) { return obj; }

void my_swift_unknownObjectRelease(void *obj) __asm__("_swift_unknownObjectRelease");
void my_swift_unknownObjectRelease(void *obj) {}

void *my_swift_unknownObjectRetain_n(void *obj, int n) __asm__("_swift_unknownObjectRetain_n");
void *my_swift_unknownObjectRetain_n(void *obj, int n) { return obj; }

void my_swift_unknownObjectRelease_n(void *obj, int n) __asm__("_swift_unknownObjectRelease_n");
void my_swift_unknownObjectRelease_n(void *obj, int n) {}

void *my_swift_unownedRetain(void *obj) __asm__("_swift_unownedRetain");
void *my_swift_unownedRetain(void *obj) { return obj; }

void my_swift_unownedRelease(void *obj) __asm__("_swift_unownedRelease");
void my_swift_unownedRelease(void *obj) {}

void *my_swift_unownedRetainStrong(void *obj) __asm__("_swift_unownedRetainStrong");
void *my_swift_unownedRetainStrong(void *obj) { return obj; }

void *my_swift_unownedRetainStrongAndRelease(void *obj) __asm__("_swift_unownedRetainStrongAndRelease");
void *my_swift_unownedRetainStrongAndRelease(void *obj) { return obj; }

void *my_swift_nonatomic_unownedRetainStrong(void *obj) __asm__("_swift_nonatomic_unownedRetainStrong");
void *my_swift_nonatomic_unownedRetainStrong(void *obj) { return obj; }

void *my_swift_nonatomic_unownedRetainStrongAndRelease(void *obj) __asm__("_swift_nonatomic_unownedRetainStrongAndRelease");
void *my_swift_nonatomic_unownedRetainStrongAndRelease(void *obj) { return obj; }

void *my_swift_unownedCheck(void *obj) __asm__("_swift_unownedCheck");
void *my_swift_unownedCheck(void *obj) { return obj; }

void *my_swift_unknownObjectUnownedInit(void *dest, void *val) __asm__("_swift_unknownObjectUnownedInit");
void *my_swift_unknownObjectUnownedInit(void *dest, void *val) { if (dest) *(void**)dest = val; return dest; }

void *my_swift_unknownObjectUnownedAssign(void *dest, void *val) __asm__("_swift_unknownObjectUnownedAssign");
void *my_swift_unknownObjectUnownedAssign(void *dest, void *val) { if (dest) *(void**)dest = val; return dest; }

void *my_swift_unknownObjectUnownedLoadStrong(void **ref) __asm__("_swift_unknownObjectUnownedLoadStrong");
void *my_swift_unknownObjectUnownedLoadStrong(void **ref) { return ref ? *ref : (void*)0; }

void my_swift_unknownObjectUnownedDestroy(void *dest) __asm__("_swift_unknownObjectUnownedDestroy");
void my_swift_unknownObjectUnownedDestroy(void *dest) { if (dest) *(void**)dest = (void*)0; }

void *my_swift_unknownObjectWeakInit(void *dest, void *val) __asm__("_swift_unknownObjectWeakInit");
void *my_swift_unknownObjectWeakInit(void *dest, void *val) { if (dest) *(void**)dest = val; return dest; }

void *my_swift_unknownObjectWeakAssign(void *dest, void *val) __asm__("_swift_unknownObjectWeakAssign");
void *my_swift_unknownObjectWeakAssign(void *dest, void *val) { if (dest) *(void**)dest = val; return dest; }

void *my_swift_unknownObjectWeakLoadStrong(void **ref) __asm__("_swift_unknownObjectWeakLoadStrong");
void *my_swift_unknownObjectWeakLoadStrong(void **ref) { return ref ? *ref : (void*)0; }

void my_swift_unknownObjectWeakDestroy(void *dest) __asm__("_swift_unknownObjectWeakDestroy");
void my_swift_unknownObjectWeakDestroy(void *dest) { if (dest) *(void**)dest = (void*)0; }

void *my_swift_weakInit(void *dest, void *val) __asm__("_swift_weakInit");
void *my_swift_weakInit(void *dest, void *val) { if (dest) *(void**)dest = val; return dest; }

void *my_swift_weakAssign(void *dest, void *val) __asm__("_swift_weakAssign");
void *my_swift_weakAssign(void *dest, void *val) { if (dest) *(void**)dest = val; return dest; }

void *my_swift_weakLoadStrong(void **ref) __asm__("_swift_weakLoadStrong");
void *my_swift_weakLoadStrong(void **ref) { return ref ? *ref : (void*)0; }

void my_swift_weakDestroy(void *dest) __asm__("_swift_weakDestroy");
void my_swift_weakDestroy(void *dest) { if (dest) *(void**)dest = (void*)0; }

void *my_swift_weakCopyInit(void *dest, void *src) __asm__("_swift_weakCopyInit");
void *my_swift_weakCopyInit(void *dest, void *src) { if (dest && src) *(void**)dest = *(void**)src; return dest; }

void *my_swift_weakTakeInit(void *dest, void *src) __asm__("_swift_weakTakeInit");
void *my_swift_weakTakeInit(void *dest, void *src) { if (dest && src) { *(void**)dest = *(void**)src; *(void**)src = (void*)0; } return dest; }

void *my_swift_weakCopyAssign(void *dest, void *src) __asm__("_swift_weakCopyAssign");
void *my_swift_weakCopyAssign(void *dest, void *src) { if (dest && src) *(void**)dest = *(void**)src; return dest; }

void *my_swift_weakTakeAssign(void *dest, void *src) __asm__("_swift_weakTakeAssign");
void *my_swift_weakTakeAssign(void *dest, void *src) { if (dest && src) { *(void**)dest = *(void**)src; *(void**)src = (void*)0; } return dest; }

void *my_swift_getObjectType(void *obj) __asm__("_swift_getObjectType");
void *my_swift_getObjectType(void *obj) {
    if (!obj) return (void*)0;
    uintptr_t isa = *(uintptr_t*)obj;
    if (isa & 1) {
        isa &= 0x00007ffffffffff8ULL;
    }
    return (void*)isa;
}

Class my_swift_getObjCClassFromObject(void *obj) __asm__("_swift_getObjCClassFromObject");
Class my_swift_getObjCClassFromObject(void *obj) {
    return (Class)my_swift_getObjectType(obj);
}

void *my_swift_initStackObject(void *metadata, void *object) __asm__("_swift_initStackObject");
void *my_swift_initStackObject(void *metadata, void *object) {
    if (object) *(void**)object = metadata;
    return object;
}

void *my_swift_initStaticObject(void *metadata, void *object) __asm__("_swift_initStaticObject");
void *my_swift_initStaticObject(void *metadata, void *object) {
    if (object) *(void**)object = metadata;
    return object;
}

void my_swift_setDeallocating(void *object) __asm__("_swift_setDeallocating");
void my_swift_setDeallocating(void *object) {}

// Swift Type Metadata & Reflection helpers
static void* vwt_copy(void *dest, void *src, void *type) {
    if (dest && src) __builtin_memcpy(dest, src, 40);
    return dest;
}
static void vwt_destroy(void *object, void *type) {}
static unsigned int vwt_getEnumTag(const void *object, unsigned int numExtraInhabitants, void *type) {
    return 0;
}
static void vwt_storeEnumTag(void *object, unsigned int whichCase, unsigned int numExtraInhabitants, void *type) {}

static const uintptr_t my_dummy_vwt[] = {
    (uintptr_t)vwt_copy,         // 0x00: initializeBufferWithCopyOfBuffer
    (uintptr_t)vwt_destroy,      // 0x08: destroy
    (uintptr_t)vwt_copy,         // 0x10: initializeWithCopy
    (uintptr_t)vwt_copy,         // 0x18: assignWithCopy
    (uintptr_t)vwt_copy,         // 0x20: initializeWithTake
    (uintptr_t)vwt_copy,         // 0x28: assignWithTake
    (uintptr_t)vwt_getEnumTag,   // 0x30: getEnumTagSinglePayload
    (uintptr_t)vwt_storeEnumTag, // 0x38: storeEnumTagSinglePayload
    40,                          // 0x40: size = 40 bytes
    40,                          // 0x48: stride = 40 bytes
    0x00070007,                  // 0x50: flags
    0                            // 0x58: extra inhabitants
};

static const uintptr_t my_dummy_metadata_buffer[64] = {
    (uintptr_t)my_dummy_vwt, // offset -8: ValueWitnessTable
    0x303,                   // offset  0: Kind (Existential)
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1], // 10, 11 (offset 0x48, 0x50)
    (uintptr_t)&my_dummy_metadata_buffer[1], // 12 (offset 0x58)
    16,                                      // 13 (offset 0x60: field offset 1)
    24,                                      // 14 (offset 0x68: field offset 2)
    32,                                      // 15 (offset 0x70: field offset 3)
    40,                                      // 16 (offset 0x78: field offset 4)
    48,                                      // 17 (offset 0x80: field offset 5)
    56,                                      // 18 (offset 0x88: field offset 6)
    64,                                      // 19 (offset 0x90: field offset 7)
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1], (uintptr_t)&my_dummy_metadata_buffer[1],
    (uintptr_t)&my_dummy_metadata_buffer[1]
};

#define SWIFT_METADATA_PTR ((void*)&my_dummy_metadata_buffer[1])

// Memory Protection Hook for PartitionAlloc
#define MAP_PRIVATE 0x0002
#define MAP_FIXED   0x0010
#define MAP_ANON    0x1000
#define MAP_FAILED  ((void*)-1)

typedef struct interpose_s {
    const void* replacement;
    const void* replacee;
} interpose_t;

#define DYLD_INTERPOSE(_replacement, _replacee) \
   __attribute__((used)) static const interpose_t _interpose_##_replacee \
            __attribute__ ((section ("__DATA,__interpose"))) = { (const void*)(unsigned long)&_replacement, (const void*)(unsigned long)&_replacee };

extern int __mprotect(void *addr, size_t len, int prot);
extern int mprotect(void *addr, size_t len, int prot);
extern void* mmap(void *addr, size_t len, int prot, int flags, int fd, int64_t offset);
extern long write(int fd, const void *buf, size_t count);

int my_mprotect(void *addr, size_t len, int prot) __asm__("_mprotect");
int my_mprotect(void *addr, size_t len, int prot) {
    int res = __mprotect(addr, len, prot);
    if (res != 0) {
        void *mapped = mmap(addr, len, prot, MAP_PRIVATE | MAP_ANON | MAP_FIXED, -1, 0);
        if (mapped != MAP_FAILED) {
            write(2, "[tahoe_shim] mprotect fixed unmapped pages with MAP_FIXED\\n", 58);
            return 0;
        }
    }
    return res;
}

DYLD_INTERPOSE(my_mprotect, mprotect)

typedef long (*sys_mprotect_fn)(void *addr, size_t len, int prot);
static sys_mprotect_fn real_sys_mprotect = (sys_mprotect_fn)0;

long my_kernel_mprotect(void *addr, size_t len, int prot) {
    write(2, "[tahoe_shim] my_kernel_mprotect called!\\n", 41);
    long res = real_sys_mprotect ? real_sys_mprotect(addr, len, prot) : 0;
    if (res != 0) {
        void *mapped = mmap(addr, len, prot, MAP_PRIVATE | MAP_ANON | MAP_FIXED, -1, 0);
        if (mapped != MAP_FAILED) {
            write(2, "[tahoe_shim] sys_mprotect hooked: mapped uncommitted pages with MAP_FIXED\\n", 75);
            return 0;
        }
    }
    return res;
}

extern int open(const char*, int, ...);
extern long read(int, void*, size_t);
extern int close(int);
extern void *dlsym(void*, const char*);
extern unsigned long long strtoull(const char*, char**, int);
extern char *strstr(const char*, const char*);
extern char *strchr(const char*, int);
#define O_RDONLY 0
#define RTLD_DEFAULT ((void*)-2)
#define PROT_NONE 0
#define PROT_READ 1
#define PROT_WRITE 2
#define PROT_EXEC 4

#include "/home/paras/.darling/swift_patch_tables.h"

void *my_swift_initClassMetadata(void *self, size_t flags, size_t numFields, const void *fieldTypes, size_t *fieldOffsets)
    __asm__("_swift_initClassMetadata");
void *my_swift_initClassMetadata(void *self, size_t flags, size_t numFields, const void *fieldTypes, size_t *fieldOffsets) {
    return self ? self : SWIFT_METADATA_PTR;
}

void *my_swift_updateClassMetadata(void *self, size_t flags, size_t numFields, const void *fieldTypes, size_t *fieldOffsets)
    __asm__("_swift_updateClassMetadata");
void *my_swift_updateClassMetadata(void *self, size_t flags, size_t numFields, const void *fieldTypes, size_t *fieldOffsets) {
    return self ? self : SWIFT_METADATA_PTR;
}

extern void *memcpy(void*, const void*, size_t);
extern void *memmove(void*, const void*, size_t);
extern int memcmp(const void*, const void*, size_t);
extern int strcmp(const char*, const char*);
extern void bzero(void*, size_t);
extern void abort(void);

struct SwiftMetadataResponse {
    void *value;
    size_t state;
};

static void *swift_generic_fallback(void) {
    return SWIFT_METADATA_PTR;
}

static void *resolve_la_symbol(const char *name) {
    if (!name || !name[0]) return (void*)0;
    if (strcmp(name, "_memcpy") == 0 || strcmp(name, "memcpy") == 0) return (void*)&memcpy;
    if (strcmp(name, "_memmove") == 0 || strcmp(name, "memmove") == 0) return (void*)&memmove;
    if (strcmp(name, "_memset") == 0 || strcmp(name, "memset") == 0) return (void*)&memset;
    if (strcmp(name, "_memcmp") == 0 || strcmp(name, "memcmp") == 0) return (void*)&memcmp;
    if (strcmp(name, "___bzero") == 0 || strcmp(name, "bzero") == 0) return (void*)&bzero;
    if (strcmp(name, "_malloc") == 0 || strcmp(name, "malloc") == 0) return (void*)&malloc;
    if (strcmp(name, "_free") == 0 || strcmp(name, "free") == 0) return (void*)&free;
    if (strcmp(name, "_abort") == 0 || strcmp(name, "abort") == 0) return (void*)&abort;
    if (strcmp(name, "_strlen") == 0 || strcmp(name, "strlen") == 0) return (void*)&strlen;
    if (strcmp(name, "_write") == 0 || strcmp(name, "write") == 0) return (void*)&write;
    if (strcmp(name, "_read") == 0 || strcmp(name, "read") == 0) return (void*)&read;
    if (strcmp(name, "_close") == 0 || strcmp(name, "close") == 0) return (void*)&close;
    if (strcmp(name, "_open") == 0 || strcmp(name, "open") == 0) return (void*)&open;
    if (strcmp(name, "_dlsym") == 0 || strcmp(name, "dlsym") == 0) return (void*)&dlsym;
    
    void *sym = dlsym(RTLD_DEFAULT, name);
    if (!sym && name[0] == '_') sym = dlsym(RTLD_DEFAULT, name + 1);
    return sym;
}

static void *resolve_zero_patch(const char *name) {
    if (!name || !name[0]) return (void*)swift_generic_fallback;
    if (strcmp(name, "_swift_retain") == 0) return (void*)&my_swift_retain;
    if (strcmp(name, "_swift_release") == 0) return (void*)&my_swift_release;
    if (strcmp(name, "_swift_retain_n") == 0) return (void*)&my_swift_retain_n;
    if (strcmp(name, "_swift_release_n") == 0) return (void*)&my_swift_release_n;
    if (strcmp(name, "_swift_allocObject") == 0) return (void*)&my_swift_allocObject;
    if (strcmp(name, "_swift_slowAlloc") == 0) return (void*)&my_swift_slowAlloc;
    if (strcmp(name, "_swift_slowDealloc") == 0) return (void*)&my_swift_slowDealloc;
    if (strcmp(name, "_swift_deallocObject") == 0) return (void*)&my_swift_deallocObject;
    if (strcmp(name, "_swift_deallocClassInstance") == 0) return (void*)&my_swift_deallocClassInstance;
    if (strcmp(name, "_swift_deallocBox") == 0) return (void*)&my_swift_deallocBox;
    if (strcmp(name, "_swift_projectBox") == 0) return (void*)&my_swift_projectBox;
    if (strcmp(name, "_swift_beginAccess") == 0) return (void*)&my_swift_beginAccess;
    if (strcmp(name, "_swift_endAccess") == 0) return (void*)&my_swift_endAccess;
    if (strcmp(name, "_swift_unownedRetain") == 0) return (void*)&my_swift_unownedRetain;
    if (strcmp(name, "_swift_unownedRelease") == 0) return (void*)&my_swift_unownedRelease;
    if (strcmp(name, "_swift_unownedRetainStrong") == 0) return (void*)&my_swift_unownedRetainStrong;
    if (strcmp(name, "_swift_weakInit") == 0) return (void*)&my_swift_weakInit;
    if (strcmp(name, "_swift_weakAssign") == 0) return (void*)&my_swift_weakAssign;
    if (strcmp(name, "_swift_weakLoadStrong") == 0) return (void*)&my_swift_weakLoadStrong;
    if (strcmp(name, "_swift_weakDestroy") == 0) return (void*)&my_swift_weakDestroy;
    if (strcmp(name, "_swift_weakCopyInit") == 0) return (void*)&my_swift_weakCopyInit;
    if (strcmp(name, "_swift_weakTakeInit") == 0) return (void*)&my_swift_weakTakeInit;
    if (strcmp(name, "_swift_weakCopyAssign") == 0) return (void*)&my_swift_weakCopyAssign;
    if (strcmp(name, "_swift_weakTakeAssign") == 0) return (void*)&my_swift_weakTakeAssign;
    if (strcmp(name, "_swift_initClassMetadata") == 0) return (void*)&my_swift_initClassMetadata;
    if (strcmp(name, "_swift_updateClassMetadata") == 0) return (void*)&my_swift_updateClassMetadata;
    
    void *sym = dlsym(RTLD_DEFAULT, name);
    if (!sym && name[0] == '_') sym = dlsym(RTLD_DEFAULT, name + 1);
    if (!sym) sym = (void*)swift_generic_fallback;
    return sym;
}

extern int __ulock_wake(uint32_t operation, void *addr, uint64_t wake_value);

void my_os_unfair_lock_unlock(uint32_t *lock) {
    if (!lock) return;
    uint32_t old = __atomic_exchange_n(lock, 0, __ATOMIC_RELEASE);
    if (old & 1) {
        __ulock_wake(0x1000002, lock, 0);
    }
}

int my_SetSystemPagesAccess(void *addr, size_t len, int access, int tag) {
    if (!addr || len == 0) return 1;
    int prot = PROT_READ | PROT_WRITE;
    if (access == 8) prot = 0;
    int res = __mprotect(addr, len, prot);
    if (res != 0) {
        void *mapped = mmap(addr, len, prot, MAP_PRIVATE | MAP_ANON | MAP_FIXED, -1, 0);
    }
    return 1;
}

static void patch_libswiftcore(void) {
    int fd = open("/proc/self/maps", O_RDONLY);
    if (fd < 0) return;

    char buf[2048];
    long n;
    uintptr_t base = 0;
    uintptr_t arccore_base = 0;
    uintptr_t platform_base = 0;
    char line[512];
    int line_idx = 0;

    while ((n = read(fd, buf, sizeof(buf))) > 0) {
        for (long i = 0; i < n; i++) {
            char c = buf[i];
            if (c == '\\n' || line_idx >= 510) {
                line[line_idx] = '\\0';
                line_idx = 0;
                if (!base && strstr(line, "libswiftCore.dylib") && strstr(line, "r-xp")) {
                    char *dash = strchr(line, '-');
                    if (dash) {
                        *dash = '\\0';
                        base = (uintptr_t)strtoull(line, (char**)0, 16);
                    }
                }
                if (!arccore_base && strstr(line, "ArcCore") && strstr(line, "r-xp")) {
                    char *dash = strchr(line, '-');
                    if (dash) {
                        *dash = '\\0';
                        arccore_base = (uintptr_t)strtoull(line, (char**)0, 16);
                    }
                }
                if (!platform_base && strstr(line, "libsystem_platform.dylib") && strstr(line, "r-xp")) {
                    char *dash = strchr(line, '-');
                    if (dash) {
                        *dash = '\\0';
                        platform_base = (uintptr_t)strtoull(line, (char**)0, 16);
                    }
                }
            } else {
                line[line_idx++] = c;
            }
        }
    }
    close(fd);

    if (platform_base) {
        write(2, "[tahoe_shim] Found libsystem_platform.dylib, installing lock patches...\\n", 71);
        uintptr_t page_unlock = (platform_base + 0x28c0) & ~0xfffULL;
        __mprotect((void*)page_unlock, 0x1000, PROT_READ | PROT_WRITE | PROT_EXEC);
        uint8_t *tramp_unlock = (uint8_t*)(platform_base + 0x28c0);
        tramp_unlock[0] = 0x48;
        tramp_unlock[1] = 0xb8;
        void *fn_unlock = (void*)&my_os_unfair_lock_unlock;
        __builtin_memcpy(&tramp_unlock[2], &fn_unlock, 8);
        tramp_unlock[10] = 0xff;
        tramp_unlock[11] = 0xe0;
        __mprotect((void*)page_unlock, 0x1000, PROT_READ | PROT_EXEC);

        uintptr_t page_abort = (platform_base + 0x8220) & ~0xfffULL;
        __mprotect((void*)page_abort, 0x1000, PROT_READ | PROT_WRITE | PROT_EXEC);
        *(uint8_t*)(platform_base + 0x8220) = 0xc3; // __os_lock_corruption_abort
        *(uint8_t*)(platform_base + 0x8230) = 0xc3; // __os_unfair_lock_recursive_abort
        *(uint8_t*)(platform_base + 0x8240) = 0xc3; // __os_unfair_lock_unowned_abort
        *(uint8_t*)(platform_base + 0x8250) = 0xc3; // __os_unfair_lock_corruption_abort
        *(uint8_t*)(platform_base + 0x8260) = 0xc3; // __os_once_gate_recursive_abort
        *(uint8_t*)(platform_base + 0x8270) = 0xc3; // __os_once_gate_unowned_abort
        *(uint8_t*)(platform_base + 0x8280) = 0xc3; // __os_once_gate_corruption_abort
        *(uint8_t*)(platform_base + 0x8290) = 0xc3; // __os_lock_recursive_abort
        __mprotect((void*)page_abort, 0x1000, PROT_READ | PROT_EXEC);
        write(2, "[tahoe_shim] libsystem_platform lock patches successfully installed!\\n", 69);
    }

    if (!base) {
        write(2, "[tahoe_shim] libswiftCore.dylib not found in maps\\n", 51);
    } else {
        write(2, "[tahoe_shim] Found libswiftCore.dylib base, patching stubs and runtime...\\n", 75);

        // 1. Patch __TEXT,__stubs (0x3670e4, 211 stubs)
        uintptr_t stubs_page = (base + 0x3670e4) & ~0xfffULL;
        __mprotect((void*)stubs_page, 0x2000, PROT_READ | PROT_WRITE | PROT_EXEC);

        for (int i = 0; i < 211; i++) {
            uint8_t *stub = (uint8_t*)(base + 0x3670e4 + i * 6);
            uintptr_t la_ptr = base + 0x3ad958 + i * 8;

            stub[0] = 0xff;
            stub[1] = 0x25;
            int32_t disp = (int32_t)(la_ptr - ((uintptr_t)stub + 6));
            __builtin_memcpy(&stub[2], &disp, 4);

            const char *sname = swift_la_symbol_names[i];
            void *sym = resolve_la_symbol(sname);
            if (sym) {
                *(uintptr_t*)la_ptr = (uintptr_t)sym;
            }
        }
        __mprotect((void*)stubs_page, 0x2000, PROT_READ | PROT_EXEC);

        // 2. Patch the 91 zero-block functions with trampolines
        uintptr_t zero_page = (base + 0x2e2000);
        size_t zero_len = 0x28000;
        __mprotect((void*)zero_page, zero_len, PROT_READ | PROT_WRITE | PROT_EXEC);

        int num_patches = sizeof(swift_zero_patches) / sizeof(swift_zero_patches[0]);
        for (int i = 0; i < num_patches; i++) {
            const char *pname = swift_zero_patches[i].name;
            uint32_t poff = swift_zero_patches[i].offset;

            void *impl = resolve_zero_patch(pname);

            uint8_t *tramp = (uint8_t*)(base + poff);
            tramp[0] = 0x48;
            tramp[1] = 0xb8;
            __builtin_memcpy(&tramp[2], &impl, 8);
            tramp[10] = 0xff;
            tramp[11] = 0xe0;
        }
        __mprotect((void*)zero_page, zero_len, PROT_READ | PROT_EXEC);

        write(2, "[tahoe_shim] libswiftCore stubs and trampolines successfully installed!\\n", 73);
    }

    if (arccore_base) {
        write(2, "[tahoe_shim] Found ArcCore base, installing PartitionAlloc hooks...\\n", 68);
        uintptr_t page_spa = (arccore_base + 0x4dd0f90) & ~0xfffULL;
        __mprotect((void*)page_spa, 0x1000, PROT_READ | PROT_WRITE | PROT_EXEC);
        uint8_t *tramp_spa = (uint8_t*)(arccore_base + 0x4dd0f90);
        tramp_spa[0] = 0x48;
        tramp_spa[1] = 0xb8;
        void *fn_spa = (void*)&my_SetSystemPagesAccess;
        __builtin_memcpy(&tramp_spa[2], &fn_spa, 8);
        tramp_spa[10] = 0xff;
        tramp_spa[11] = 0xe0;
        __mprotect((void*)page_spa, 0x1000, PROT_READ | PROT_EXEC);

        uintptr_t page_crash = (arccore_base + 0x9494210) & ~0xfffULL;
        __mprotect((void*)page_crash, 0x2000, PROT_READ | PROT_WRITE | PROT_EXEC);
        uint8_t *tramp_crash = (uint8_t*)(arccore_base + 0x9494210);
        tramp_crash[0] = 0xc3; // ret
        uint8_t *tramp_oom = (uint8_t*)(arccore_base + 0x9494400);
        tramp_oom[0] = 0xc3; // ret
        __mprotect((void*)page_crash, 0x2000, PROT_READ | PROT_EXEC);
        write(2, "[tahoe_shim] ArcCore PartitionAlloc hooks successfully installed!\\n", 66);
    }
}

__attribute__((constructor))
static void install_tahoe_hooks(void) {
    uintptr_t mprotect_sym = (uintptr_t)&__mprotect;
    uintptr_t *slot = (uintptr_t*)(mprotect_sym + 0x56744);
    if (slot && *slot) {
        real_sys_mprotect = (sys_mprotect_fn)*slot;
        *slot = (uintptr_t)my_kernel_mprotect;
        write(2, "[tahoe_shim] Successfully installed kernel sys_mprotect hook!\\n", 63);
    }
    patch_libswiftcore();
}

void *my_swift_getExistentialTypeMetadata(uint32_t flags, const void *superclass, size_t numProtocols, const void *protocols)
    __asm__("_swift_getExistentialTypeMetadata");
void *my_swift_getExistentialTypeMetadata(uint32_t flags, const void *superclass, size_t numProtocols, const void *protocols) {
    return SWIFT_METADATA_PTR;
}

struct SwiftMetadataResponse my_swift_getGenericMetadata(size_t request, const void * const *arguments, const void *description)
    __asm__("_swift_getGenericMetadata");
struct SwiftMetadataResponse my_swift_getGenericMetadata(size_t request, const void * const *arguments, const void *description) {
    struct SwiftMetadataResponse resp;
    resp.value = SWIFT_METADATA_PTR;
    resp.state = 0;
    return resp;
}

void *my_swift_getTypeByMangledNameInContext(const char *name, size_t nameLength, const void *context, const void * const *genericArgs)
    __asm__("_swift_getTypeByMangledNameInContext");
void *my_swift_getTypeByMangledNameInContext(const char *name, size_t nameLength, const void *context, const void * const *genericArgs) {
    return SWIFT_METADATA_PTR;
}

struct SwiftMetadataResponse my_swift_getTypeByMangledNameInContextInMetadataState(size_t request, const char *name, size_t nameLength, const void *context, const void * const *genericArgs)
    __asm__("_swift_getTypeByMangledNameInContextInMetadataState");
struct SwiftMetadataResponse my_swift_getTypeByMangledNameInContextInMetadataState(size_t request, const char *name, size_t nameLength, const void *context, const void * const *genericArgs) {
    struct SwiftMetadataResponse resp;
    resp.value = SWIFT_METADATA_PTR;
    resp.state = 0;
    return resp;
}

struct SwiftMetadataResponse my_swift_getSingletonMetadata(size_t request, const void *description)
    __asm__("_swift_getSingletonMetadata");
struct SwiftMetadataResponse my_swift_getSingletonMetadata(size_t request, const void *description) {
    struct SwiftMetadataResponse resp;
    resp.value = SWIFT_METADATA_PTR;
    resp.state = 0;
    return resp;
}

void *my_swift_getMetatypeMetadata(const void *instance)
    __asm__("_swift_getMetatypeMetadata");
void *my_swift_getMetatypeMetadata(const void *instance) {
    return SWIFT_METADATA_PTR;
}

void *my_swift_getExistentialMetatypeMetadata(const void *instance)
    __asm__("_swift_getExistentialMetatypeMetadata");
void *my_swift_getExistentialMetatypeMetadata(const void *instance) {
    return SWIFT_METADATA_PTR;
}

struct SwiftMetadataResponse my_swift_getOpaqueTypeMetadata(size_t request, const void *args, const void *desc, size_t index)
    __asm__("_swift_getOpaqueTypeMetadata");
struct SwiftMetadataResponse my_swift_getOpaqueTypeMetadata(size_t request, const void *args, const void *desc, size_t index) {
    struct SwiftMetadataResponse resp;
    resp.value = SWIFT_METADATA_PTR;
    resp.state = 0;
    return resp;
}

const void *my_swift_getWitnessTable(const void *conformance, const void *type, const void * const *instantiationArgs)
    __asm__("_swift_getWitnessTable");
const void *my_swift_getWitnessTable(const void *conformance, const void *type, const void * const *instantiationArgs) {
    return (const void*)my_dummy_vwt;
}

const void *my_swift_getAssociatedTypeWitness(size_t request, const void *wtable, const void *conformingType, const void *reqBase, const void *assocType)
    __asm__("_swift_getAssociatedTypeWitness");
const void *my_swift_getAssociatedTypeWitness(size_t request, const void *wtable, const void *conformingType, const void *reqBase, const void *assocType) {
    return SWIFT_METADATA_PTR;
}

const void *my_swift_getAssociatedConformanceWitness(const void *wtable, const void *conformingType, const void *assocType, const void *reqBase, const void *assocConf)
    __asm__("_swift_getAssociatedConformanceWitness");
const void *my_swift_getAssociatedConformanceWitness(const void *wtable, const void *conformingType, const void *assocType, const void *reqBase, const void *assocConf) {
    return (const void*)my_dummy_vwt;
}

void *my_swift_dynamicCastObjCProtocolConditional(void *object, const void *protocol)
    __asm__("_swift_dynamicCastObjCProtocolConditional");
void *my_swift_dynamicCastObjCProtocolConditional(void *object, const void *protocol) {
    return object;
}

const void *my_swift_conformsToProtocol(const void *type, const void *protocol)
    __asm__("_swift_conformsToProtocol");
const void *my_swift_conformsToProtocol(const void *type, const void *protocol) {
    return (const void*)1;
}

Class my_swift_getObjCClassFromMetadata(const void *metadata)
    __asm__("_swift_getObjCClassFromMetadata");
Class my_swift_getObjCClassFromMetadata(const void *metadata) {
    if (!metadata) return (Class)0;
    uintptr_t val = (uintptr_t)metadata;
    if (val & 1) val &= 0x00007ffffffffff8ULL;
    return (Class)val;
}

void *my_swift_getObjCClassMetadata(Class cls)
    __asm__("_swift_getObjCClassMetadata");
void *my_swift_getObjCClassMetadata(Class cls) {
    return (void*)cls;
}

void *my_foundation_url_metadata(void)
    __asm__("_$s10Foundation3URLVMa");
void *my_foundation_url_metadata(void) {
    return SWIFT_METADATA_PTR;
}

struct SwiftStringPair my_url_lastPathComponent(void)
    __asm__("_$s10Foundation3URLV17lastPathComponentSSvg");
struct SwiftStringPair my_url_lastPathComponent(void) {
    return make_swift_string("Arc", 3);
}

struct SwiftStringPair my_url_pathExtension(void)
    __asm__("_$s10Foundation3URLV13pathExtensionSSvg");
struct SwiftStringPair my_url_pathExtension(void) {
    return make_swift_string("app", 3);
}

struct SwiftStringPair my_url_path(void)
    __asm__("_$s10Foundation3URLV4pathSSvg");
struct SwiftStringPair my_url_path(void) {
    return make_swift_string("/Applications/Arc.app", 21);
}

// System file/directory helpers
int my_copyfile(const char *from, const char *to, void *state, uint32_t flags) __asm__("_copyfile");
int my_copyfile(const char *from, const char *to, void *state, uint32_t flags) { return 0; }

int my_dirhelper(int type, char *buffer, size_t buflen) __asm__("___dirhelper");
int my_dirhelper(int type, char *buffer, size_t buflen) { return 0; }
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

out.append('\n// Functions (Type accessors return SWIFT_METADATA_PTR, others NULL)')
for idx, fn in enumerate(sorted(functions)):
    safe_id = f"fn_{idx:05d}"
    out.append(f'void* {safe_id}(void) __asm__("{fn}");')
    if fn.endswith('Ma') or fn.endswith('ML') or fn.endswith('Mm'):
        out.append(f'void* {safe_id}(void) {{ return SWIFT_METADATA_PTR; }}')
    else:
        out.append(f'void* {safe_id}(void) {{ return (void*)0; }}')

content = '\n'.join(out)
out_path = pathlib.Path('/home/paras/.darling/usr/lib/tahoe_shim_full.m')
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Wrote {out_path} ({len(content)} bytes)')
