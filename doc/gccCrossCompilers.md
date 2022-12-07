# Installing and using cross compilers on Debian/Ubuntu

see: [Cross compiling for arm or aarch64 on Debian or
Ubuntu](https://jensd.be/1126/linux/cross-compiling-for-arm-or-aarch64-on-debian-or-ubuntu)

## x86_64 build machine -> aarch64 run (host) machine

To install:

```
sudo apt install gcc make gcc-aarch64-linux-gnu binutils-aarch64-linux-gnu
```

To build:

```
aarch64-linux-gnu-gcc <<args>>
```

## aarch64 build machine -> x86_64 run (host) machine

To install:

```
sudo apt install gcc make gcc-x86-64-linux-gnu binutils-x86-64-linux-gnu
```

To build:

```
x86_64-linux-gnu-gcc <<args>>
```
