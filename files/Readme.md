# pySockets based Compute Pods

Since the Ninja Build system can not interrupt any of its jobs, there is
essentially no need/way to interrupt the pySockets workers.

This means we can keep the workers fairly simple.


## Notes on workers required for a "complete" solution

We need:

1. ConTeXt (can be setup on both x86_64 and arm64 machines)

   We will need a number of specialist ConTeXt modules to provide
   information to the build system about what needs to be built.

2. gcc/llvm (can be setup on both x86_64 and arm64 machines, and can be
   setup to cross compile to either architecture)

3. (ANSI-C) Code verification software
   1. frama-c : https://frama-c.com/

     Uses Opam to provide a (rather complex) installation (x86_64 only?)

   2. Verifast : https://github.com/verifast/verifast

      To build it requires:
        - ocaml ocaml-num
        - Z3
        - GTK+ GtkSourceView lablgtk
        - gcc/llvm
     and (I think) will not build on arm64...

     To run we can simply download nightly binary builds (which will only
     work on x86_64 machines)

4. joyLoL (We build this ourselves and so can be used on both x86_64 and
   arm64 machines)

   May (eventually) require gcc/llvm as well as Z3 (x86_64 only - might be
   able to compile z3 ourselves on arm64 - we could use either the C or
   Python APIs)

5. Z3 : https://github.com/Z3Prover/z3

   We could use the native z3 command line binary or our own C or a Python
   based interface to the libz3 library.

## Securing system

We will use ssh tunnels to secure the communication between the
requesters, the taskManager and the various workers.

This has the added advantage that a tunnel can be constructed across the
internet, for use when away from home.

## Distributing working files between remote computers

We will use sshfs to provide secure remote file system access. This has
the added advantage that it will work across the internet, for use when
away from home.

## Starting a system...

We will use Ansible to start local and remote workers, the taskManager,
all required sshfs file systems as well as all required ssh tunnels.
