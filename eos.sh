sudo useradd -m -G wheel -s /bin/zsh ilya
sudo passwd ilya

sudo pacman -S zsh-autosuggestions zsh-syntax-highlighting
sudo pacman -S firefox plasma sddm konsole dolphin
sudo systemctl enable sddm
sudo systemctl status sddm
sudo pacman -S networkmanager
sudo systemctl enable NetworkManager
sudo systemctl start NetworkManager
sudo pacman -S linux-firmware
sudo pacman -S wl-clipboard
sudo pacman -S endeavouros-branding eos-settings-plasma eos-breeze-sddm
