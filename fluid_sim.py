"""
Based on the Jos Stam paper https://www.researchgate.net/publication/2560062_Real-Time_Fluid_Dynamics_for_Games
and the mike ash vulgarization https://mikeash.com/pyblog/fluid-simulation-for-dummies.html
"""
import numpy as np
import math

class Fluid:

    def __init__(self):
        self.size = 50  # map size
        self.dt = 0.5  # time interval
        self.iter = 8  # linear equation solving iteration number

        self.diff = 0.0000  # Diffusion
        self.visc = 0.0000  # viscosity

        self.s = np.full((self.size, self.size), 0, dtype=float)
        self.density = np.full((self.size, self.size), 0, dtype=float)

        # array of 2d vectors, [x, y]
        self.velo = np.full((self.size, self.size, 2), 0, dtype=float)
        self.velo0 = np.full((self.size, self.size, 2), 0, dtype=float)

    @property
    def total_density(self):
        """Gives the total density amount, ignoring boundaries corrections"""
        return self.density[1:-1, 1:-1].sum()

    @property
    def vector_divergence(self):
        """Compute vector divergence by pixel: (left - right) * x_component + (top - down) * y_component"""
        divergence_map = np.full((self.size, self.size), 0, dtype=float)
        for x in range(1, self.size-2):
            for y in range(1, self.size-2):
                velocity_window = self.velo[y-1:y+2, x-1:x+2]
                divergence_map[y, x] = (np.gradient(velocity_window[:, :, 0], axis=0) +
                                        np.gradient(velocity_window[:, :, 1], axis=1)).sum()

        return divergence_map

    @property
    def total_divergence(self):
        """Sum of the absolute divergence value"""
        return np.abs(self.vector_divergence).sum()

    def step(self):
        self.diffuse(self.velo0, self.velo, self.visc)

        # x0, y0, x, y
        self.project(self.velo0[:, :, 0], self.velo0[:, :, 1], self.velo[:, :, 0], self.velo[:, :, 1])

        self.advect(self.velo[:, :, 0], self.velo0[:, :, 0], self.velo0)
        self.advect(self.velo[:, :, 1], self.velo0[:, :, 1], self.velo0)

        self.project(self.velo[:, :, 0], self.velo[:, :, 1], self.velo0[:, :, 0], self.velo0[:, :, 1])

        self.diffuse(self.s, self.density, self.diff)

        self.advect(self.density, self.s, self.velo)

    def lin_solve(self, x, x0, a, c):
        c_recip = 1 / c

        for iteration in range(0, self.iter):
            x[1:-1, 1:-1] = (x0[1:-1, 1:-1] + a * (x[2:, 1:-1] + x[:-2, 1:-1] + x[1:-1, 2:] + x[1:-1, :-2])) * c_recip

            self.set_boundaries(x)

    def set_boundaries(self, table):
        """
        Boundaries handling. For density, border reflection may affect the total density sum
        :return:
        """

        if len(table.shape) > 2:  # 3d velocity vector array
            # vertical borders
            table[:, 0, 0] = table[:, 1, 0]
            table[:, 0, 1] = - table[:, 1, 1]
            table[:, -1, 0] = table[:, -2, 0]
            table[:, -1, 1] = - table[:, -2, 1]

            # horizontal borders
            table[0, :, 0] = - table[1, :, 0]
            table[0, :, 1] = table[1, :, 1]
            table[-1, :, 0] = - table[-2, :, 0]
            table[-1, :, 1] = table[-2, :, 1]

        else:
            table[:, 0] = table[:, 1]
            table[:, -1] = table[:, -2]

            table[0, :] = table[1, :]
            table[-1, :] = table[-2, :]

        #  pass through boundaries (loop over walls)
        # table[:, 0] = table[:, -2]
        # table[:, -1] = table[:, 1]
        #
        # table[0, :] = table[-2, :]
        # table[-1, :] = table[1, :]

        # corners
        table[0, 0] = 0.5 * (table[1, 0] + table[0, 1])
        table[0, -1] = 0.5 * (table[1, -1] + table[0, -2])
        table[-1, 0] = 0.5 * (table[-2, 0] + table[- 1, 1])
        table[-1, -1] = 0.5 * (table[-2, -1] + table[-1, -2])

    def diffuse(self, x, x0, diff):
        if diff != 0:
            a = self.dt * diff * (self.size - 2) * (self.size - 2)
            self.lin_solve(x, x0, a, 1 + 6 * a)
        else:  # equivalent to lin_solve with a = 0
            x[:, :] = x0[:, :]

    def project(self, velo_x, velo_y, p, div):

        # numpy equivalent to this in a for loop:
        # div[i, j] = -0.5 * (velo_x[i + 1, j] - velo_x[i - 1, j] + velo_y[i, j + 1] - velo_y[i, j - 1]) / self.size
        div[1:-1, 1:-1] = -0.5 * (
                velo_x[2:, 1:-1] -
                velo_x[:-2, 1:-1] +
                velo_y[1:-1, 2:] -
                velo_y[1:-1, :-2]) \
                          / self.size
        p[:, :] = 0

        self.set_boundaries(div)
        self.set_boundaries(p)
        self.lin_solve(p, div, 1, 6)

        velo_x[1:-1, 1:-1] -= 0.5 * (p[2:, 1:-1] - p[:-2, 1:-1]) * self.size
        velo_y[1:-1, 1:-1] -= 0.5 * (p[1:-1, 2:] - p[1:-1, :-2]) * self.size

        self.set_boundaries(self.velo)

    def advect(self, d, d0, velocity):
        """Basically move elements forward in time"""
        dtx = self.dt * (self.size - 2)
        dty = self.dt * (self.size - 2)

        for j in range(1, self.size - 1):
            for i in range(1, self.size - 1):

                tmp1 = dtx * velocity[i, j, 0]
                tmp2 = dty * velocity[i, j, 1]
                x = i - tmp1
                y = j - tmp2

                if x < 0.5:
                    x = 0.5
                if x > self.size + 0.5:
                    x = self.size + 0.5
                i0 = math.floor(x)
                i1 = i0 + 1.0

                if y < 0.5:
                    y = 0.5
                if y > self.size + 0.5:
                    y = self.size + 0.5
                j0 = math.floor(y)
                j1 = j0 + 1.0

                s1 = x - i0
                s0 = 1.0 - s1
                t1 = y - j0
                t0 = 1.0 - t1

                i0i = int(i0)
                i1i = int(i1)
                j0i = int(j0)
                j1i = int(j1)

                d[i, j] = s0 * (t0 * d0[i0i, j0i] + t1 * d0[i0i, j1i]) + \
                          s1 * (t0 * d0[i1i, j0i] + t1 * d0[i1i, j1i])

        self.set_boundaries(d)


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from matplotlib import animation

    # Enable for pycharm users
    # import matplotlib
    # matplotlib.use('Qt5Agg')

    inst = Fluid()



    def on_move(event):
        if event.inaxes:
            # print(f'data coords {event.xdata} {event.ydata},',
            #     f'pixel coords {event.x} {event.y}')
            inst.density[int(event.ydata)-2:int(event.ydata)+2, int(event.xdata)-2:int(event.xdata)+2] += 100

    def update_im(i):
        inst.velo[5, 5] += [2, 2]
        inst.step()
        im.set_array(inst.density)
        # update vector field data
        q.set_UVC(inst.velo[:, :, 1], inst.velo[:, :, 0])

        # ! slows down processing if enabled
        # print(f"Density sum: {inst.total_density:.2f}, Total divergence: {inst.total_divergence:.2f}")

        # auto adjust heatmap "brightness"
        im.autoscale()

    fig = plt.figure()

    # plot density (set interpolation to none for raw view)
    im = plt.imshow(inst.density, cmap='hot', vmax=100, interpolation='bilinear')

    # plot vector field
    q = plt.quiver(inst.velo[:, :, 1], inst.velo[:, :, 0], scale=10, angles='xy', color='black')
    binding_id = plt.connect('motion_notify_event', on_move)

    anim = animation.FuncAnimation(fig, update_im, interval=0)
    plt.show()
