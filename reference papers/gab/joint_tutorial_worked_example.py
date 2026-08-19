#!/usr/bin/env python3
"""The worked example of joint_demodulation_decoding_tutorial.tex (JCM-288).

Every number on the worked-example frames is printed by this script and
copied into the deck unchanged, rounded to four decimals.  The conventions
match the executable receiver's partial-FFT views (pfft_blocks.jl in
Rpchan): M contiguous equal segments and a unitary FFT.  The setting
follows the partial-FFT page of the ofdm-doppler-site: FFT bin 4 watching
carrier 5, common offset 0.20, M=4 windows.
"""
import numpy as np

N, M = 8, 4
delta = 0.20   # the common offset of the site example, in bins
n = np.arange(N)
F = np.exp(-2j*np.pi*np.outer(n, n)/N)/np.sqrt(N)     # unitary DFT
G = np.diag(np.exp(2j*np.pi*delta*n/N))               # the channel operator
S = [np.diag((n//(N//M) == m).astype(float)) for m in range(M)]

H = F @ G @ F.conj().T                                # channel coefficients
C = np.stack([F @ S[m] @ G @ F.conj().T for m in range(M)])   # C[m, k, q]

print("== the channel: common offset 0.20, N=8, M=4 ==")
print("delta=0 would give H = I exactly:",
      np.allclose(F @ F.conj().T, np.eye(N)))
print(f"|H[4,4]|={abs(H[4,4]):.4f}  |H[4,3]|={abs(H[4,3]):.4f}  "
      f"|H[4,5]|={abs(H[4,5]):.4f}")

print("\n== (25) and (29) at k=4 ==")
for q in (4, 5):
    parts = [C[m, 4, q] for m in range(M)]
    for m, c in enumerate(parts, start=1):
        print(f"q={q}: c{m}={c:.4f}")
    print(f"q={q}: sum={sum(parts):.4f}  H={H[4,q]:.4f}")
print("max |sum_m c_(k,q,m) - H_(k,q)| over all pairs:",
      f"{np.abs(C.sum(0) - H).max():.1e}")

print("\n== (24) and the symbol variance ==")
z1, z2 = 4.0, -1.0
xi1, xi2 = np.tanh(z1/2), np.tanh(z2/2)
s = (xi1 + 1j*xi2)/np.sqrt(2)
print(f"z=({z1:g},{z2:g})  xi=({xi1:.4f},{xi2:.4f})  s={s:.4f}")
print(f"|s|^2={abs(s)**2:.4f}  v=1-|s|^2={1-abs(s)**2:.4f}")

print("\n== (27): one view, two ways ==")
rng = np.random.default_rng(7)
bits = rng.integers(0, 2, size=(N, 2))
X = ((1-2*bits[:, 0]) + 1j*(1-2*bits[:, 1]))/np.sqrt(2)   # hard QPSK
r = G @ F.conj().T @ X                                    # received block
Y_direct = (F @ S[0] @ r)[4]
Y_model = (C[0] @ X)[4]
print(f"windowed FFT of the received block: {Y_direct:.4f}")
print(f"coefficient mix sum_q c_(4,q,1) X_q: {Y_model:.4f}")
print(f"difference: {abs(Y_direct-Y_model):.1e}")

print("\n== (30): the terms ==")
sigma = 0.05
noise = sigma*(rng.standard_normal(N)+1j*rng.standard_normal(N))/np.sqrt(2)
r_n = r + noise
resid = sum(np.linalg.norm(F @ S[m] @ r_n - C[m] @ X)**2 for m in range(M))
print(f"signal term at the true pair, sigma={sigma:g}: {resid:.4f}")
xi3 = np.tanh(3.0/2)
sat = xi1*(-abs(xi2))*(-xi3)      # signs (+,-,-): the check is satisfied
bad = xi1*(-abs(xi2))*(+xi3)      # signs (+,-,+): one sign is wrong
print(f"parity check over three bits, xi magnitudes "
      f"({xi1:.4f}, {abs(xi2):.4f}, {xi3:.4f}):")
print(f"  hard bits, even parity: product +1, penalty 0")
print(f"  relaxed, correct signs: product {sat:+.4f}, penalty {(1-sat)**2:.4f}")
print(f"  relaxed, one wrong sign: product {bad:+.4f}, penalty {(1-bad)**2:.4f}")

# Gradient-step strip (CL-197).  The coefficients are held at their true
# values, and plain gradient steps with a fixed step size move only z.  The
# receiver instead solves C conditionally and moves z with Adam.
print("\n== gradient steps on z: the ring and the objective ==")
lam_d, lam_p = 1.0, 0.08
btrue = np.empty(2*N)
btrue[0::2], btrue[1::2] = 1 - 2*bits[:, 0], 1 - 2*bits[:, 1]

# three-bit parity checks that the true bits satisfy
checks, pool = [], list(range(2*N))
while len(pool) >= 3:
    tri, rest, j = pool[:3], pool[3:], 0
    while np.prod(btrue[tri]) < 0 and j < len(rest):
        tri, j = pool[:2] + [rest[j]], j + 1
    checks.append(tri)
    pool = [i for i in pool if i not in tri]

Y_obs = [F @ S[m] @ r_n for m in range(M)]

def objective(zv):
    xi = np.tanh(zv/2)
    s_all = (xi[0::2] + 1j*xi[1::2])/np.sqrt(2)
    sig = sum(np.linalg.norm(Y_obs[m] - C[m] @ s_all)**2 for m in range(M))
    par = sum((1 - np.prod(xi[list(c)]))**2 for c in checks)
    return lam_d*sig + lam_p*par

def gradient(zv, h=1e-6):
    g = np.zeros_like(zv)
    for i in range(zv.size):
        zp, zm = zv.copy(), zv.copy()
        zp[i] += h
        zm[i] -= h
        g[i] = (objective(zp) - objective(zm))/(2*h)
    return g

z_desc = 0.8*btrue
eta = 0.8
g0 = gradient(z_desc)
print(f"carrier 4 starts at z_4=({z_desc[8]:.4f},{z_desc[9]:.4f}); "
      f"the t=0 gradient there is ({g0[8]:.4f},{g0[9]:.4f})")
print(f"step size eta={eta:g}, so the first move of z_4 is "
      f"({-eta*g0[8]:+.4f},{-eta*g0[9]:+.4f})")
cube = next(c for c in checks if 8 in c)
corner = "".join("0" if btrue[i] > 0 else "1" for i in cube)
print(f"the check containing carrier 4's first bit is over bits {tuple(cube)}; "
      f"its codeword corner is {corner}")
print(f"the t=0 gradient on that triple is "
      f"({g0[cube[0]]:.4f},{g0[cube[1]]:.4f},{g0[cube[2]]:.4f})")
print(f"with eta={eta:g} the triple's first move is "
      f"({-eta*g0[cube[0]]:+.4f},{-eta*g0[cube[1]]:+.4f},"
      f"{-eta*g0[cube[2]]:+.4f})")
for t in range(9):
    if t:
        z_desc = z_desc - eta*gradient(z_desc)
    xi_d = np.tanh(z_desc/2)
    s4 = (xi_d[8] + 1j*xi_d[9])/np.sqrt(2)
    v4 = 1 - (xi_d[8]**2 + xi_d[9]**2)/2
    vmean = 1 - ((xi_d[0::2]**2 + xi_d[1::2]**2)/2).mean()
    print(f"t={t}: J={objective(z_desc):.4f}  "
          f"z_4=({z_desc[8]:.4f},{z_desc[9]:.4f})  "
          f"xi_4=({xi_d[8]:.4f},{xi_d[9]:.4f})  s_4={s4:.4f}  "
          f"v_4={v4:.4f}  mean v={vmean:.4f}")
    tri = xi_d[list(cube)]
    pen = (1 - np.prod(tri))**2
    print(f"     cube triple xi=({tri[0]:.4f},{tri[1]:.4f},{tri[2]:.4f})  "
          f"check penalty={pen:.4f}")
    ax = np.sqrt(1 - xi_d[[8, 9, cube[0]]]**2)
    print(f"     ball semi-axes sqrt(1-xi^2) over (xi_8,xi_9,xi_2)="
          f"({ax[0]:.4f},{ax[1]:.4f},{ax[2]:.4f})")
