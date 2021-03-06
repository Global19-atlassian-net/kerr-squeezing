import numpy as np
import matplotlib.pyplot as plt
from kerrlib import P_loss, P_no_loss, gaussian, rect, sech, lorentzian, myfft


class qss:

    def __init__(self, zf, n):
        r"""Sets up simulation.

        Args:
            zf (float): End points (-zf, +zf) of real-space array.
            n (int): Number of points in real-space array. Should be odd.
        """
        # Constant parameters
        self.c = 299792458  # speed of light [m/s]

        # Set up z- and k-space arrays
        self.zf = zf
        self.n = n
        self.zz = np.linspace(-self.zf, self.zf, self.n)
        self.dz = self.zz[1] - self.zz[0]
        self.kk = np.fft.fftfreq(self.n, d=self.dz) * (2 * np.pi)
        self.ks = np.fft.fftshift(self.kk)
        self.dk = self.kk[1] - self.kk[0]

    def evolution(self, L, G, T0, P0, ng, b2, g,
                  u=None, loss=False, TN=None, TD=None, scale_factor=10**10):
        r"""Evolves mean field through nonlinear channel waveguide, returning evolved field as well
          as N and M moments.

        Args:
            L (float): Waveguide length [m].
            G (float): Loss rate [Hz*10^10].
            T0 (float): Pulse FWHM [s].
            P0 (float): Pump power [W].
            ng (float): Group index.
            b2 (float): Group velocity dispersion [s^2/m].
            g (float): Nonlinear parameter [/m/W].
            u (string or array): Mean field in z-space. Can be one of the strings {"Gaussian",
              "Rect", "Sech", "Lorentzian"} or a user specified array. Note that each requires
              its own conversion from FWHM duration to "unit width" duration.
            loss (bool): Toggle for lossless vs lossy evolution.
            TN (float): Nonlinear time [s*10^-10]. Derived parameter unless specified here.
            TD (float): Diserpsion time [s*10^-10]. Derived parameter unless specified here.

        Returns:
            u (float(n)): Evolved mean field.
            M (float(n,n)): M moment.
            N (float(n,n)): N moment.
        """

        # Set default mean-field in z-space
        if u is None:
            u = gaussian(self.zz)
            T0 = T0 / (2 * np.sqrt(np.log(2)))  # pulse 1/e width [s]
        # Enable user to speficy any of the four built-in functions, or their own
        if type(u) is str:
            if u == "Gaussian":
                u = gaussian(self.zz)
                T0 = T0 / (2 * np.sqrt(np.log(2)))  # pulse 1/e width [s]
            elif u == "Rect":
                u = rect(self.zz)
            elif u == "Sech":
                u = sech(self.zz)
                T0 = T0 / (2 * np.sqrt(1 + np.log(np.sqrt(2))))
            elif u == "Lorentzian":
                u = lorentzian(self.zz)
            else:
                raise ValueError(f"{u} is not a valid pump shape.")
        if len(u) != self.n:
            raise ValueError(f"Pump shape function is not length {self.n}.")

        # Derived parameters
        v = self.c / ng          # group velocity
        if TN is None:
            TN = 1 / (g * P0 * v) * scale_factor  # scaled nonlinear time
        if TD is None:
            TD = (T0 * v)**2 / (b2 * v**3) * scale_factor  # scaled dispersion time

        self.dt = self.dz
        # number of points in time (final time=dt*tf)
        self.tf = np.rint(L / (v * self.dt) * scale_factor).astype(int)

        # Set up k-space grid
        xx, yy = np.meshgrid(self.ks, self.ks) / self.dk
        im = np.rint(xx - yy) + (self.n - 1) / 2
        ip = np.rint(xx + yy) + (self.n - 1) / 2
        im = np.clip(im, 0, self.n - 1).astype(int)
        ip = np.clip(ip, 0, self.n - 1).astype(int)

        # Perform Evolution
        if not loss:
            u, M, N = P_no_loss(u, TD, TN, self.dz, self.kk, self.ks,
                                self.dk, im, ip, self.tf, self.dt, self.n)
        else:
            u, M, N = P_loss(u, TD, TN, G, self.dz, self.kk, self.ks,
                             self.dk, im, ip, self.tf, self.dt, self.n)
        return u, M, N

    def plot_m(self, M):
        r"""Plots M moment (JSA).

        Args:
            M (float(n,n)): M moment.
        """
        plt.matshow(np.abs(M)**2, origin="lower")
        plt.show()

    def plot_evolution(self, u_ev, u=None):
        r"""Plots evolution of mean field in real and reciprocal space.

        Args:
            u_ev (float(n)): Evolved mean field.
            u (array): Mean field in z-space.
        """
        if u is None:
            u = gaussian(self.zz)
        if len(u) != self.n:
            raise ValueError(f"Pump shape function is not length {self.n}.")
        fig, (ax1, ax2) = plt.subplots(1, 2)
        ax1.set_xlim(-self.zf, self.zf)
        ax1.plot(self.zz, np.abs(u)**2)
        ax1.plot(self.zz, np.abs(u_ev)**2)
        ax2.set_xlim(-self.zf, self.zf)
        ax2.plot(self.ks, np.abs(myfft(u, self.dz))**2)
        ax2.plot(self.ks, np.abs(myfft(u_ev, self.dz))**2)
        plt.show()

    def squeezing(self, u_ev, M, N):
        r"""Determiniation of squeezing as measured in a homodyne measurement with a local
        oscillator corresponding to the evolved mean field.

        Args:
            u_ev (float(n)): Evolved mean field.
            M (float(n,n)): M moment.
            N (float(n,n)): N moment.

        Returns:
            phi (float(100)): Local oscillator phase array from 0 to pi.
            sq (float(100)): Squeezing in dB as measured in a homodyne measurement with a local
              oscillator corresponding to the evolved mean field.
        """
        phi = np.linspace(0, np.pi, 100)
        f = myfft(u_ev, self.dz)
        f /= np.linalg.norm(f)

        p1 = f.conj() @ M @ f.conj().T
        p2 = f @ N @ f.conj().T

        q1 = np.exp(2j * np.linspace(0, np.pi, 100)) * p1
        q2 = p2
        tp = q1 + q1.conj() + 2 * q2 + 1
        sq = 10 * np.log10(tp.real)
        return phi, sq

    def plot_squeezing(self, phi, sq):
        r"""Plots squeezing in dB.

        Args:
            phi (float(100)): Local oscillator phase array from 0 to pi.
            sq (float(100)): Squeezing in dB as measured in a homodyne measurement with a local
              oscillator corresponding to the evolved mean field.
        """
        fig, ax = plt.subplots()
        ax.plot(phi, sq)
        plt.show()
