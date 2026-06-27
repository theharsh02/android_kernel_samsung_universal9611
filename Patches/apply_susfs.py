#!/usr/bin/env python3
"""Apply SUSFS v2.0.0 to KernelSU-Next (post-reorganization layout, run from KernelSU-Next/)."""
import sys

def read(path):
    with open(path, 'r', errors='replace') as f:
        return f.read()

def write(path, content):
    with open(path, 'w') as f:
        f.write(content)

def require(path, content, marker, label="marker"):
    if marker not in content:
        print(f"ERROR: {path}: {label} not found:\n  {marker[:80]!r}", file=sys.stderr)
        sys.exit(1)

def done(path):
    print(f"  OK: {path}")

# ── kernel/Kbuild ──────────────────────────────────────────────────────────────
def patch_kbuild():
    p = 'kernel/Kbuild'
    c = read(p)
    if 'SUSFS_VERSION' in c:
        print(f"  skip (already patched): {p}"); return
    m = '# Keep a new line here!!'
    require(p, c, m)
    ins = (
        '## For susfs stuff ##\n'
        'ifeq ($(shell test -e $(srctree)/fs/susfs.c; echo $$?),0)\n'
        '$(eval SUSFS_VERSION=$(shell cat $(srctree)/include/linux/susfs.h'
        ' | grep -E \'^#define SUSFS_VERSION\' | cut -d\' \' -f3 | sed \'s/"//g\'))\n'
        '$(info )\n'
        '$(info -- SUSFS_VERSION: $(SUSFS_VERSION))\n'
        'else\n'
        '$(info -- You have not integrated susfs in your kernel yet.)\n'
        '$(info -- Read: https://gitlab.com/simonpunk/susfs4ksu)\n'
        'endif\n\n'
    )
    write(p, c.replace(m, ins + m, 1))
    done(p)

# ── kernel/Kconfig ─────────────────────────────────────────────────────────────
SUSFS_KCONFIG_MENU = '''
menu "KernelSU - SUSFS"
config KSU_SUSFS
    bool "KernelSU addon - SUSFS"
    depends on KSU
    depends on THREAD_INFO_IN_TASK
    default y
    help
        Patch and Enable SUSFS to kernel with KernelSU.

config KSU_SUSFS_SUS_PATH
    bool "Enable to hide suspicious path (NOT recommended)"
    depends on KSU_SUSFS
    default y
    help
        Allow hiding user-defined path and sub-paths from various syscalls.

config KSU_SUSFS_SUS_MOUNT
    bool "Enable to hide suspicious mounts"
    depends on KSU_SUSFS
    default y
    help
        Allow hiding user-defined mount paths from /proc/self/mounts.

config KSU_SUSFS_SUS_KSTAT
    bool "Enable to spoof suspicious kstat"
    depends on KSU_SUSFS
    default y
    help
        Allow spoofing kstat of user-defined file/directory.

config KSU_SUSFS_TRY_UMOUNT
	bool "Enable to use ksu's try_umount"
	depends on KSU_SUSFS
	default y
	help
		Allow using try_umount for user-defined mount paths.

config KSU_SUSFS_SPOOF_UNAME
    bool "Enable to spoof uname"
    depends on KSU_SUSFS
    default y
    help
        Allow spoofing the string returned by uname syscall.

config KSU_SUSFS_ENABLE_LOG
    bool "Enable logging susfs log to kernel"
    depends on KSU_SUSFS
    default y
    help
        Allow logging susfs log to kernel.

config KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS
    bool "Enable to automatically hide ksu and susfs symbols from /proc/kallsyms"
    depends on KSU_SUSFS
    default y
    help
        Automatically hide ksu and susfs symbols from /proc/kallsyms.

config KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
    bool "Enable to spoof /proc/bootconfig (gki) or /proc/cmdline (non-gki)"
    depends on KSU_SUSFS
    default y
    help
        Spoof /proc/bootconfig or /proc/cmdline with a user-defined file.

config KSU_SUSFS_OPEN_REDIRECT
    bool "Enable to redirect a path to be opened with another path (experimental)"
    depends on KSU_SUSFS
    default y
    help
        Allow redirecting a target path to another user-defined path.

config KSU_SUSFS_SUS_MAP
    bool "Enable to hide some mmapped real file from /proc/<pid>/maps"
    depends on KSU_SUSFS
    default y
    help
        Allow hiding mmapped real file from proc maps interfaces.

endmenu
'''

def patch_kconfig():
    p = 'kernel/Kconfig'
    c = read(p)
    if 'KSU_SUSFS' in c:
        print(f"  skip (already patched): {p}"); return
    idx = c.rfind('\nendmenu\n')
    if idx == -1:
        idx = c.rfind('\nendmenu')
    if idx == -1:
        print(f"ERROR: {p}: endmenu not found", file=sys.stderr); sys.exit(1)
    write(p, c[:idx] + SUSFS_KCONFIG_MENU + c[idx:])
    done(p)

# ── kernel/core/init.c ─────────────────────────────────────────────────────────
def patch_core_init():
    p = 'kernel/core/init.c'
    c = read(p)
    if 'susfs.h' in c:
        print(f"  skip (already patched): {p}"); return

    m1 = '#include "selinux/selinux.h"'
    require(p, c, m1)
    c = c.replace(m1,
        m1 + '\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs.h>\n#endif', 1)

    m2 = 'ksu_throne_tracker_init();'
    require(p, c, m2)
    c = c.replace(m2,
        m2 + '\n\n#ifdef CONFIG_KSU_SUSFS\n\t\tsusfs_init();\n#endif', 1)

    write(p, c); done(p)

# ── kernel/feature/kernel_umount.c ────────────────────────────────────────────
def patch_kernel_umount_c():
    p = 'kernel/feature/kernel_umount.c'
    c = read(p)
    if 'CONFIG_KSU_SUSFS' in c:
        print(f"  skip (already patched): {p}"); return

    m = 'static bool ksu_kernel_umount_enabled = true;'
    require(p, c, m)
    c = c.replace(m,
        '#ifndef CONFIG_KSU_SUSFS\n'
        'static bool ksu_kernel_umount_enabled = true;\n'
        '#else\n'
        'bool ksu_kernel_umount_enabled = true;\n'
        '#endif', 1)

    m = 'static void try_umount(const char *mnt, int flags)'
    require(p, c, m)
    c = c.replace(m,
        '#if !defined(CONFIG_KSU_SUSFS) || !defined(CONFIG_KSU_SUSFS_TRY_UMOUNT)\n'
        'static void try_umount(const char *mnt, int flags)\n'
        '#else\n'
        'void try_umount(const char *mnt, int flags)\n'
        '#endif', 1)

    m = 'static void umount_tw_func('
    require(p, c, m)
    c = c.replace(m,
        '#if !defined(CONFIG_KSU_SUSFS) || !defined(CONFIG_KSU_SUSFS_TRY_UMOUNT)\n'
        'static void umount_tw_func(', 1)

    m = '\nvoid __init ksu_kernel_umount_init'
    require(p, c, m)
    c = c.replace(m,
        '\n#endif // !defined(CONFIG_KSU_SUSFS) || !defined(CONFIG_KSU_SUSFS_TRY_UMOUNT)\n'
        '\nvoid __init ksu_kernel_umount_init', 1)

    write(p, c); done(p)

# ── kernel/feature/kernel_umount.h ────────────────────────────────────────────
def patch_kernel_umount_h():
    p = 'kernel/feature/kernel_umount.h'
    c = read(p)
    if 'CONFIG_KSU_SUSFS' in c:
        print(f"  skip (already patched): {p}"); return

    m = 'int ksu_handle_umount(uid_t old_uid, uid_t new_uid);'
    require(p, c, m)
    c = c.replace(m,
        '#if !defined(CONFIG_KSU_SUSFS) || !defined(CONFIG_KSU_SUSFS_TRY_UMOUNT)\n'
        'int ksu_handle_umount(uid_t old_uid, uid_t new_uid);\n'
        '#endif\n\n'
        '#ifdef CONFIG_KSU_SUSFS\n'
        'extern bool ksu_kernel_umount_enabled;\n'
        '#endif', 1)

    write(p, c); done(p)

# ── kernel/hook/setuid_hook.c ─────────────────────────────────────────────────
SUSFS_SETUID_HELPERS = '''
#ifdef CONFIG_KSU_SUSFS
static inline bool is_zygote_isolated_service_uid(uid_t uid)
{
    uid %= 100000;
    return (uid >= 99000 && uid < 100000);
}

static inline bool is_zygote_normal_app_uid(uid_t uid)
{
    uid %= 100000;
    return (uid >= 10000 && uid < 19999);
}

extern u32 susfs_zygote_sid;
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
extern void susfs_run_sus_path_loop(uid_t uid);
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
extern void susfs_reorder_mnt_id(void);
#endif
#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
extern void susfs_try_umount(uid_t uid);
#endif
#endif // CONFIG_KSU_SUSFS
'''

SUSFS_DO_UMOUNT = '''
#if !defined(CONFIG_KSU_SUSFS) || !defined(CONFIG_KSU_SUSFS_TRY_UMOUNT)
    // Handle kernel umount
    ksu_handle_umount(old_uid, new_uid);
#endif

    return 0;

#ifdef CONFIG_KSU_SUSFS
do_umount:
#ifndef CONFIG_KSU_SUSFS_TRY_UMOUNT
    ksu_handle_umount(old_uid, new_uid);
#else
    susfs_try_umount(new_uid);
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
    susfs_reorder_mnt_id();
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
    susfs_run_sus_path_loop(new_uid);
#endif
    susfs_set_current_proc_umounted();
    return 0;
#endif // CONFIG_KSU_SUSFS
}'''

def patch_setuid_hook():
    p = 'kernel/hook/setuid_hook.c'
    c = read(p)
    if 'susfs_def.h' in c:
        print(f"  skip (already patched): {p}"); return

    m = '#include "compat/kernel_compat.h"'
    require(p, c, m)
    c = c.replace(m,
        m + '\n#ifdef CONFIG_KSU_SUSFS\n#include <linux/susfs_def.h>\n#endif', 1)

    m = 'extern void disable_seccomp(struct task_struct *tsk);'
    require(p, c, m)
    c = c.replace(m, m + SUSFS_SETUID_HELPERS, 1)

    # Insert zygote check + isolated service check before pr_debug
    for prefix in ['\t', '    ']:
        m = f'{prefix}pr_debug("handle_setresuid from %d to %d\\n", old_uid, new_uid);'
        if m in c:
            zygote_check = (
                f'\n{prefix}if (!susfs_is_sid_equal(current_cred(), susfs_zygote_sid))\n'
                f'{prefix}\treturn 0;\n\n'
                f'#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n'
                f'{prefix}if (is_zygote_isolated_service_uid(new_uid))\n'
                f'{prefix}\tgoto do_umount;\n'
                f'#endif\n\n'
            )
            c = c.replace(m, zygote_check + m, 1)
            break
    else:
        print(f"WARNING: {p}: pr_debug marker not found, zygote check skipped", file=sys.stderr)

    # After is_uid_manager block opening brace add goto do_umount for manager
    m = 'if (unlikely(is_uid_manager(new_uid))) {'
    if m in c:
        mgr_goto = (
            '\n#ifdef CONFIG_KSU_SUSFS\n'
            '\t\tgoto do_umount;\n'
            '#else\n'
        )
        # find the brace and insert after it, before the #if LINUX_VERSION_CODE
        c = c.replace(m, m + mgr_goto, 1)
        # close the else after the manager block
        # find the matching else/end of manager block by looking for "} else {"
        c = c.replace('\n\t} else {\n', '\n#endif // CONFIG_KSU_SUSFS\n\t} else {\n', 1)

    # Replace final ksu_handle_umount + return 0 with SUSFS do_umount block
    # Try several possible forms
    for old_end in [
        '\n\t// Handle kernel umount\n\tksu_handle_umount(old_uid, new_uid);\n\n\treturn 0;\n}',
        '\n    // Handle kernel umount\n    ksu_handle_umount(old_uid, new_uid);\n\n    return 0;\n}',
        '\n\tksu_handle_umount(old_uid, new_uid);\n\n\treturn 0;\n}',
    ]:
        if old_end in c:
            c = c.replace(old_end, SUSFS_DO_UMOUNT, 1)
            break
    else:
        print(f"WARNING: {p}: end-of-function replacement not found", file=sys.stderr)

    write(p, c); done(p)

# ── kernel/selinux/rules.c ────────────────────────────────────────────────────
def patch_selinux_rules():
    p = 'kernel/selinux/rules.c'
    c = read(p)
    if 'susfs_set_zygote_sid' in c:
        print(f"  skip (already patched): {p}"); return

    m = 'ksu_allow(db, "system_server", KERNEL_SU_DOMAIN, "process", "sigkill");'
    require(p, c, m)
    c = c.replace(m, m + '\n\n#ifdef CONFIG_KSU_SUSFS\n'
        '\tsusfs_set_priv_app_sid();\n'
        '\tsusfs_set_init_sid();\n'
        '\tsusfs_set_ksu_sid();\n'
        '\tsusfs_set_zygote_sid();\n'
        '#endif', 1)
    write(p, c); done(p)

# ── kernel/selinux/selinux.c ──────────────────────────────────────────────────
SUSFS_SELINUX_FUNCTIONS = '''#ifdef CONFIG_KSU_SUSFS
#define KERNEL_INIT_DOMAIN "u:r:init:s0"
#define KERNEL_ZYGOTE_DOMAIN "u:r:zygote:s0"
#define KERNEL_PRIV_APP_DOMAIN "u:r:priv_app:s0:c512,c768"

u32 susfs_ksu_sid = 0;
u32 susfs_init_sid = 0;
u32 susfs_zygote_sid = 0;
u32 susfs_priv_app_sid = 0;

static inline void susfs_set_sid(const char *secctx_name, u32 *out_sid)
{
    int err;
    if (!secctx_name || !out_sid) { pr_err("susfs_set_sid: NULL arg\\n"); return; }
    err = security_secctx_to_secid(secctx_name, strlen(secctx_name), out_sid);
    if (err) { pr_err("susfs_set_sid: failed for '%s': %d\\n", secctx_name, err); return; }
    pr_info("susfs_set_sid: sid %u for '%s'\\n", *out_sid, secctx_name);
}

bool susfs_is_sid_equal(const struct cred *cred, u32 sid2)
{
#if LINUX_VERSION_CODE < KERNEL_VERSION(6, 18, 0)
    const struct task_security_struct *tsec = selinux_cred(cred);
#else
    const struct cred_security_struct *tsec = selinux_cred(cred);
#endif
    if (!tsec) return false;
    return tsec->sid == sid2;
}

u32 susfs_get_sid_from_name(const char *secctx_name)
{
    u32 out_sid = 0;
    int err;
    if (!secctx_name) { pr_err("susfs_get_sid_from_name: NULL\\n"); return 0; }
    err = security_secctx_to_secid(secctx_name, strlen(secctx_name), &out_sid);
    if (err) { pr_err("susfs_get_sid_from_name: failed '%s': %d\\n", secctx_name, err); return 0; }
    return out_sid;
}

u32 susfs_get_current_sid(void) { return current_sid(); }

void susfs_set_zygote_sid(void)        { susfs_set_sid(KERNEL_ZYGOTE_DOMAIN,   &susfs_zygote_sid); }
bool susfs_is_current_zygote_domain(void) { return unlikely(current_sid() == susfs_zygote_sid); }
void susfs_set_ksu_sid(void)           { susfs_set_sid(KERNEL_SU_CONTEXT,      &susfs_ksu_sid); }
bool susfs_is_current_ksu_domain(void)   { return unlikely(current_sid() == susfs_ksu_sid); }
void susfs_set_init_sid(void)          { susfs_set_sid(KERNEL_INIT_DOMAIN,     &susfs_init_sid); }
bool susfs_is_current_init_domain(void)  { return unlikely(current_sid() == susfs_init_sid); }
void susfs_set_priv_app_sid(void)      { susfs_set_sid(KERNEL_PRIV_APP_DOMAIN, &susfs_priv_app_sid); }
#endif // CONFIG_KSU_SUSFS

'''

def patch_selinux_c():
    p = 'kernel/selinux/selinux.c'
    c = read(p)
    if 'susfs_ksu_sid' in c:
        print(f"  skip (already patched): {p}"); return

    # Insert before the fake SELinux status page block
    for marker in [
        '/* --------------- fake SELinux status page --------------- */',
        '/* --------------- fake SELinux',
    ]:
        if marker in c:
            c = c.replace(marker, SUSFS_SELINUX_FUNCTIONS + marker, 1)
            write(p, c); done(p)
            return

    print(f"ERROR: {p}: fake SELinux marker not found", file=sys.stderr); sys.exit(1)

# ── kernel/selinux/selinux.h ──────────────────────────────────────────────────
SUSFS_SELINUX_DECLS = '''#ifdef CONFIG_KSU_SUSFS
bool susfs_is_sid_equal(const struct cred *cred, u32 sid2);
u32 susfs_get_sid_from_name(const char *secctx_name);
u32 susfs_get_current_sid(void);
void susfs_set_zygote_sid(void);
bool susfs_is_current_zygote_domain(void);
void susfs_set_ksu_sid(void);
bool susfs_is_current_ksu_domain(void);
void susfs_set_init_sid(void);
bool susfs_is_current_init_domain(void);
void susfs_set_priv_app_sid(void);
#endif // CONFIG_KSU_SUSFS

'''

def patch_selinux_h():
    p = 'kernel/selinux/selinux.h'
    c = read(p)
    if 'susfs_is_sid_equal' in c:
        print(f"  skip (already patched): {p}"); return

    idx = c.rfind('#endif')
    if idx == -1:
        print(f"ERROR: {p}: #endif not found", file=sys.stderr); sys.exit(1)
    write(p, c[:idx] + SUSFS_SELINUX_DECLS + c[idx:])
    done(p)

# ── kernel/supercall/dispatch.c ───────────────────────────────────────────────
SUSFS_DISPATCH_CMDS = '''
#ifdef CONFIG_KSU_SUSFS
\t\t\tsusfs_start_sdcard_monitor_fn();
#endif'''

def patch_dispatch_c():
    p = 'kernel/supercall/dispatch.c'
    c = read(p)
    if 'susfs_start_sdcard_monitor_fn' in c:
        print(f"  skip (already patched): {p}"); return

    # Add include — struct kstat forward-decl avoids -Wvisibility from susfs.h:194
    m = '#include <linux/string.h>'
    if m in c:
        c = c.replace(m,
            '#ifdef CONFIG_KSU_SUSFS\nstruct kstat;\n#include <linux/susfs.h>\n#endif\n' + m, 1)

    # Add sdcard monitor after on_boot_completed()
    m = 'on_boot_completed();'
    require(p, c, m)
    c = c.replace(m, m + SUSFS_DISPATCH_CMDS, 1)

    # do_manage_mark guard is intentionally NOT changed — ksu_get_task_mark etc.
    # only exist with KSU_KPROBES_HOOK; SUSFS uses reboot syscall path instead.

    write(p, c); done(p)

# ── kernel/supercall/supercall.c ──────────────────────────────────────────────
SUSFS_REBOOT_DISPATCH = '''
#ifdef CONFIG_KSU_SUSFS
\tif (magic2 == SUSFS_MAGIC && current_uid().val == 0) {
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
\t\tif (cmd == CMD_SUSFS_ADD_SUS_PATH) { susfs_add_sus_path(arg); return 0; }
\t\tif (cmd == CMD_SUSFS_ADD_SUS_PATH_LOOP) { susfs_add_sus_path_loop(arg); return 0; }
\t\tif (cmd == CMD_SUSFS_SET_ANDROID_DATA_ROOT_PATH) { susfs_set_i_state_on_external_dir(arg); return 0; }
\t\tif (cmd == CMD_SUSFS_SET_SDCARD_ROOT_PATH) { susfs_set_i_state_on_external_dir(arg); return 0; }
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
\t\tif (cmd == CMD_SUSFS_HIDE_SUS_MNTS_FOR_NON_SU_PROCS) { susfs_set_hide_sus_mnts_for_non_su_procs(arg); return 0; }
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
\t\tif (cmd == CMD_SUSFS_ADD_SUS_KSTAT) { susfs_add_sus_kstat(arg); return 0; }
\t\tif (cmd == CMD_SUSFS_UPDATE_SUS_KSTAT) { susfs_update_sus_kstat(arg); return 0; }
\t\tif (cmd == CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY) { susfs_add_sus_kstat(arg); return 0; }
#endif
#ifdef CONFIG_KSU_SUSFS_TRY_UMOUNT
\t\tif (cmd == CMD_SUSFS_ADD_TRY_UMOUNT) { susfs_add_try_umount(arg); return 0; }
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
\t\tif (cmd == CMD_SUSFS_SET_UNAME) { susfs_set_uname(arg); return 0; }
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
\t\tif (cmd == CMD_SUSFS_ENABLE_LOG) { susfs_enable_log(arg); return 0; }
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
\t\tif (cmd == CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG) { susfs_set_cmdline_or_bootconfig(arg); return 0; }
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
\t\tif (cmd == CMD_SUSFS_ADD_OPEN_REDIRECT) { susfs_add_open_redirect(arg); return 0; }
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MAP
\t\tif (cmd == CMD_SUSFS_ADD_SUS_MAP) { susfs_add_sus_map(arg); return 0; }
#endif
\t\tif (cmd == CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING) { susfs_set_avc_log_spoofing(arg); return 0; }
\t\tif (cmd == CMD_SUSFS_SHOW_ENABLED_FEATURES) { susfs_get_enabled_features(arg); return 0; }
\t\tif (cmd == CMD_SUSFS_SHOW_VARIANT) { susfs_show_variant(arg); return 0; }
\t\tif (cmd == CMD_SUSFS_SHOW_VERSION) { susfs_show_version(arg); return 0; }
\t\treturn 0;
\t}
#endif // CONFIG_KSU_SUSFS
'''

def patch_supercall_c():
    p = 'kernel/supercall/supercall.c'
    c = read(p)
    if 'susfs_is_boot_completed_triggered' in c:
        print(f"  skip (already patched): {p}"); return

    # Add includes — struct kstat forward-decl avoids -Wvisibility from susfs.h:194
    m = '#include "uapi/supercall.h"'
    require(p, c, m)
    c = c.replace(m,
        '#ifdef CONFIG_KSU_SUSFS\n'
        '#include <linux/namei.h>\n'
        'struct kstat;\n'
        '#include <linux/susfs.h>\n'
        '#include "selinux/objsec.h"\n'
        '#endif\n' + m, 1)

    # Add boot_completed bool
    m = 'uint32_t ksuver_override = 0;'
    require(p, c, m)
    c = c.replace(m,
        m + '\n\n#ifdef CONFIG_KSU_SUSFS\n'
        'bool susfs_is_boot_completed_triggered __read_mostly = false;\n'
        '#endif', 1)

    # Insert SUSFS command dispatch after magic1 check
    m = '\tif (magic1 != KSU_INSTALL_MAGIC1)\n\t\treturn 0;'
    require(p, c, m)
    c = c.replace(m, m + SUSFS_REBOOT_DISPATCH, 1)

    # Fix kprobe guards
    c = c.replace(
        '#ifdef KSU_KPROBES_HOOK\nstatic int reboot_handler_pre',
        '#if defined(KSU_KPROBES_HOOK) && !defined(CONFIG_KSU_SUSFS)\nstatic int reboot_handler_pre', 1)
    c = c.replace(
        '#ifdef KSU_KPROBES_HOOK\n\tint rc = register_kprobe',
        '#if defined(KSU_KPROBES_HOOK) && !defined(CONFIG_KSU_SUSFS)\n\tint rc = register_kprobe', 1)
    c = c.replace(
        '#ifdef KSU_KPROBES_HOOK\n\tunregister_kprobe',
        '#if defined(KSU_KPROBES_HOOK) && !defined(CONFIG_KSU_SUSFS)\n\tunregister_kprobe', 1)

    write(p, c); done(p)

# ── main ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("Applying SUSFS v2.0.0 patches...")
    patch_kbuild()
    patch_kconfig()
    patch_core_init()
    patch_kernel_umount_c()
    patch_kernel_umount_h()
    patch_setuid_hook()
    patch_selinux_rules()
    patch_selinux_c()
    patch_selinux_h()
    patch_dispatch_c()
    patch_supercall_c()
    print("Done.")
