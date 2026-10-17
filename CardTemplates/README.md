# Card backgrounds

The card is composed from a race background and a transparent full-body
character layer. Replace these files with artist-made templates while keeping
the filenames:

- `races/human.png`
- `races/orc.png`
- `races/elf.png`
- `characters/human.png`
- `characters/orc.png`
- `characters/elf.png`

Backgrounds are portrait 2:3 images. Leave a clear strip at the top for the
character name and a panel near the bottom for text. Character layers are
portrait 2:3 PNGs with transparent backgrounds, full body, feet at the bottom,
and the right hand extended near waist height. The viewer scales the figure by
the character's size.

Weapon overlays are selected from the character's `weapon` value. Replace these
transparent PNGs while keeping their filenames:

- `weapons/katana.png`
- `weapons/axe.png`
- `weapons/sword.png`
- `weapons/pistol.png`
- `weapons/tank.png`
- `weapons/portal_cannon.png`

The `Без оружия` value has no overlay. Weapon images are scaled down and placed
over the race background, just behind the character layer, so the hand sits in
front of the grip. The card also draws a colored aura for powers.
