## Build and install for Arch Linux

```sh
cd packaging/arch/
makepkg -si -D python-txtorcon-socks5/
makepkg -si -D magic-wormhole-socks5-git/
```

or `makepkg -s` (not `-si`) and then:

```sh
sudo pacman -U \
    python-txtorcon-socks5/python-txtorcon-socks5-26.6.0-1-any.pkg.tar.zst \
    magic-wormhole-socks5-git-0.24.0.r2414.gefd192f-1-any.pkg.tar.zst
```

