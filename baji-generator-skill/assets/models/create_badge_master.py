import math
from pathlib import Path

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

verts = []
faces = []
groups = []


def add_group(name, vv, ff):
    start = len(verts)
    verts.extend(vv)
    faces.extend(tuple(start + i for i in f) for f in ff)
    groups.append((name, len(faces) - len(ff), len(faces)))


def badge_body(radius=29.0, radial=90, angular=256):
    vv, ff = [], []
    layer = 1 + radial * angular
    # Axis: X is depth; +X front, -X rear. Y/Z form the round face.
    for side in (0, 1):
        # One shared pole vertex avoids the non-manifold fan produced by
        # hundreds of coincident centre vertices.
        centre_x = 3.23 if side == 0 else -0.72
        vv.append((centre_x, 0.0, 0.0))
        for j in range(1, radial + 1):
            r = radius * j / radial
            q = r / radius
            if side == 0:
                # A shallow pressed-metal dome: almost flat in the printable centre,
                # then a smooth rolled-down shoulder close to the edge.
                dome = 2.65 * (1.0 - q ** 2.15)
                shoulder = 0.72 * (1.0 / (1.0 + math.exp(-(q - 0.88) * 34.0)))
                x = 0.58 + dome - shoulder
            else:
                # Recessed rear pan with a deeper rolled perimeter.
                pan = 0.86 * (1.0 - math.exp(-((q / 0.72) ** 8)))
                rim = 0.62 * (1.0 / (1.0 + math.exp(-(q - 0.86) * 35.0)))
                x = -0.72 - pan - rim
            for i in range(angular):
                a = 2 * math.pi * i / angular
                vv.append((x, r * math.cos(a), r * math.sin(a)))
    def idx(side, j, i=0):
        base = side * layer
        return base if j == 0 else base + 1 + (j-1)*angular + (i % angular)
    for side in (0, 1):
        # Pole fan.
        for i in range(angular):
            ni=(i+1)%angular
            ff.append((idx(side,0), idx(side,1,i), idx(side,1,ni)))
        for j in range(1, radial):
            for i in range(angular):
                ni = (i + 1) % angular
                a, b = idx(side,j,i), idx(side,j,ni)
                c, d = idx(side,j+1,ni), idx(side,j+1,i)
                ff.append((a, b, c)); ff.append((a, c, d))
    # Join the front and rear perimeter into one watertight rolled edge.
    for i in range(angular):
        ni = (i + 1) % angular
        a = idx(0,radial,i)
        b = idx(0,radial,ni)
        c = idx(1,radial,ni)
        d = idx(1,radial,i)
        ff.append((a, b, c)); ff.append((a, c, d))
    return vv, ff


def uv_sphere(center, radii, rings=20, seg=32):
    cx, cy, cz = center; rx, ry, rz = radii
    vv, ff = [], []
    for j in range(rings + 1):
        p = math.pi * j / rings
        for i in range(seg):
            a = 2 * math.pi * i / seg
            vv.append((cx + rx*math.cos(p), cy + ry*math.sin(p)*math.cos(a), cz + rz*math.sin(p)*math.sin(a)))
    for j in range(rings):
        for i in range(seg):
            ni=(i+1)%seg; a=j*seg+i; b=j*seg+ni; c=(j+1)*seg+ni; d=(j+1)*seg+i
            ff.append((a,b,c)); ff.append((a,c,d))
    return vv, ff


def tube(points, radius=0.55, seg=16):
    vv, ff = [], []
    for pidx, (x,y,z) in enumerate(points):
        # Tubes in this model mostly run in Y/Z; rings lie in X/Z.
        for i in range(seg):
            a=2*math.pi*i/seg
            vv.append((x+radius*math.cos(a), y, z+radius*math.sin(a)))
    for j in range(len(points)-1):
        for i in range(seg):
            ni=(i+1)%seg; a=j*seg+i; b=j*seg+ni; c=(j+1)*seg+ni; d=(j+1)*seg+i
            ff.append((a,b,c)); ff.append((a,c,d))
    return vv, ff


def write_obj(path):
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# Parametric 58 mm button badge master; units: millimetres\n")
        f.write("mtllib badge_master.mtl\n")
        for x,y,z in verts: f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        for name, lo, hi in groups:
            if name == "badge_shell":
                for local, face in enumerate(faces[lo:hi]):
                    if local == 0: f.write("g front_art\nusemtl front_art\n")
                    elif local == 44800: f.write("g rim_metal\nusemtl rim_metal\n")
                    elif local == 45824: f.write("g back_shell\nusemtl back_metal\n")
                    f.write("f " + " ".join(str(i+1) for i in face) + "\n")
            else:
                f.write(f"g {name}\nusemtl back_metal\n")
                for face in faces[lo:hi]: f.write("f " + " ".join(str(i+1) for i in face) + "\n")


add_group("badge_shell", *badge_body())
# Rear pin: a raised straight steel needle, hinge and safety clasp.
pin_points=[(-3.25, -13.2 + i*0.55, 1.6 + 0.12*math.sin(math.pi*i/48)) for i in range(49)]
add_group("pin_needle", *tube(pin_points, 0.38, 14))
add_group("pin_hinge", *uv_sphere((-3.05,-14.2,1.6),(1.15,1.45,1.65),18,28))
add_group("pin_clasp", *uv_sphere((-3.05,14.2,1.6),(1.35,1.75,1.45),18,28))
# Two small mounting feet make the mechanism visibly attached to the rear pan.
add_group("hinge_foot", *uv_sphere((-2.05,-13.8,0.0),(1.0,2.15,2.1),18,28))
add_group("clasp_foot", *uv_sphere((-2.05,13.8,0.0),(1.0,2.3,1.8),18,28))

obj = OUT / "badge_master_58mm.obj"
write_obj(obj)
(OUT / "badge_master.mtl").write_text(
    "newmtl front_art\nKd 1 1 1\nKs .32 .32 .32\nNs 220\n\n"
    "newmtl rim_metal\nKd .72 .74 .76\nKs .68 .68 .68\nNs 260\n\n"
    "newmtl back_metal\nKd .64 .67 .70\nKs .42 .44 .46\nNs 120\n",
    encoding="utf-8")
(OUT / "README.txt").write_text(
    "58 mm parametric button-badge master\n"
    "Units: millimetres. X is depth; +X is front.\n"
    "Front centre is smoothly domed; perimeter is thin and rolled.\n"
    "Rear pan is recessed and includes a separate needle, hinge and clasp.\n"
    "Import OBJ at scale 1.0. Subdivision is already dense; do not add heavy smoothing blindly.\n",
    encoding="utf-8")
print(obj)
