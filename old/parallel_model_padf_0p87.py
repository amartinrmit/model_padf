"""
Parallel Model PADF Calculator

@author: andrewmartin, jack-binns
"""

import numpy as np
import time
import multiprocessing as mp
import numba
import math as m
import matplotlib.pyplot as plt
import os


@numba.njit()
def fast_vec_angle(x1, x2, x3, y1, y2, y3):
    """
    Returns the angle between two vectors
    in range 0 - 90 deg
    :return theta in radians
    """
    mag1 = m.sqrt(x1 ** 2 + x2 ** 2 + x3 ** 2)
    mag2 = m.sqrt(y1 ** 2 + y2 ** 2 + y3 ** 2)
    dot = x1 * y1 + x2 * y2 + x3 * y3
    o = m.acos(dot / (mag1 * mag2))
    if 0.0 <= o < m.pi:
        return o
    else:
        return -1.0


@numba.njit()
def fast_vec_difmag(x1, x2, x3, y1, y2, y3):
    """
    :return: Magnitude of difference between two vectors
    """
    return m.sqrt((y1 - x1) ** 2 + (y2 - x2) ** 2 + (y3 - x3) ** 2)


@numba.njit()
def fast_vec_subtraction(x1, x2, x3, y1, y2, y3):
    """
    Vector subtraction vastly accelerated up by njit
    :return:
    """
    return [(y1 - x1), (y2 - x2), (y3 - x3)]


def make_interaction_sphere(probe, center, atoms):
    sphere = []
    for tar_1 in atoms:
        r_ij = fast_vec_difmag(center[0], center[1], center[2], tar_1[0], tar_1[1], tar_1[2])
        if r_ij != 0.0 and r_ij <= probe:
            sphere.append(tar_1)
    return sphere


def subject_atom_reader(raw, ucds):
    """
    An exceedingly ungainly function for reading
    in various file types
    """
    print("Finding the subject atoms [subject_atom_reader]...")
    if raw[-3:] == 'cif':
        atom_loop_count = 0  # counts the number of _atom_ labels
        atoms = []
        with open(raw, 'r') as foo:
            for line in foo:
                if '_atom_site_' in line:
                    atom_loop_count += 1
        with open(raw, 'r') as foo:
            if atom_loop_count == 8:
                for line in foo:
                    sploot = line.split()
                    if len(sploot) == atom_loop_count:  # VESTA TYPE
                        if sploot[7] != 'H':
                            if "(" in sploot[2]:
                                subsploot = sploot[2].split("(")
                                raw_x = float(subsploot[0])
                            else:
                                raw_x = float(sploot[2])
                            if "(" in sploot[3]:
                                subsploot = sploot[3].split("(")
                                raw_y = float(subsploot[0])
                            else:
                                raw_y = float(sploot[3])
                            if "(" in sploot[4]:
                                subsploot = sploot[4].split("(")
                                raw_z = float(subsploot[0])
                            else:
                                raw_z = float(sploot[4])
                            raw_atom = [float(raw_x * ucds[0]), float(raw_y * ucds[1]),
                                        float(raw_z * ucds[2])]
                            atoms.append(raw_atom)
            elif atom_loop_count == 5:  # AM TYPE
                for line in foo:
                    sploot = line.split()
                    if len(sploot) == atom_loop_count:
                        if sploot[1][0] != 'H':
                            if "(" in sploot[2]:
                                subsploot = sploot[2].split("(")
                                raw_x = float(subsploot[0])
                            else:
                                raw_x = float(sploot[2])
                            if "(" in sploot[3]:
                                subsploot = sploot[3].split("(")
                                raw_y = float(subsploot[0])
                            else:
                                raw_y = float(sploot[3])
                            if "(" in sploot[4]:
                                subsploot = sploot[4].split("(")
                                raw_z = float(subsploot[0])
                            else:
                                raw_z = float(sploot[4])
                            raw_atom = [float(raw_x * ucds[0]), float(raw_y * ucds[1]),
                                        float(raw_z * ucds[2])]
                            atoms.append(raw_atom)
    elif raw[-3:] == 'xyz':
        atoms = read_xyz(raw)
    else:
        print("WARNING: model_padf couldn't understand your subject_atom_name")
        atoms = []
    print("Asymmetric unit contains ", len(atoms), " atoms found in ", raw)
    np.array(atoms)

    return atoms


def read_xyz(file):
    print("Finding extended atom set [read_xyz]...")
    raw_x = []
    raw_y = []
    raw_z = []
    with open(file, "r") as xyz:
        for line in xyz:
            splot = line.split()
            if len(splot) == 4:
                raw_x.append(splot[1])
                raw_y.append(splot[2])
                raw_z.append(splot[3])
            elif len(splot) == 3:
                raw_x.append(splot[0])
                raw_y.append(splot[1])
                raw_z.append(splot[2])
    raw_x = [float(x) for x in raw_x]
    raw_y = [float(y) for y in raw_y]
    raw_z = [float(z) for z in raw_z]
    raw_atoms = np.column_stack((raw_x, raw_y, raw_z))
    print("Extended atom set contains ", len(raw_x), " atoms found in " + file)
    return raw_atoms


def cossim_measure(array_a, array_b):
    array_a = np.ndarray.flatten(array_a)
    array_b = np.ndarray.flatten(array_b)
    sim = np.dot(array_a, array_b) / (np.linalg.norm(array_a) * np.linalg.norm(array_b))
    return sim


class ModelPADF:

    def __init__(self):

        self.root = "/Users/andrewmartin/Work/Teaching/2020/ONPS2186/codes/model-padf-master/"
        self.project = "1al1/"
        self.xyz_name = "1al1_ex.xyz"  # the xyz file contains the cartesian coords of the crystal structure expanded
        # to include r_probe
        self.subject_atom_name = "1al1_edit.cif"  # the cif containing the asymmetric unit
        self.ucds = [62.35000, 62.35000, 62.35000, 90.0000, 90.0000, 90.0000]
        # probe radius
        self.r_probe = 10.0
        self.angular_bin = 2.0
        self.r_dist_bin = 0.1
        self.probe_theta_bin = 10.0
        self.r_power = 2
        self.convergence_check_flag = False
        self.mode = 'rrprime'
        self.dimension = 2
        self.logname = "parameter_log_file.txt"
        self.processor_num = 2
        self.Pool = mp.Pool(self.processor_num)
        self.loops = 0
        self.verbosity = 0
        self.fourbody = True
        self.Theta = np.zeros(0)
        self.subject_set = []
        self.subject_number = 1
        self.raw_extended_atoms = []
        self.extended_atoms = []
        self.loop_similarity_array = []
        self.convergence_target = 1.0
        self.converged_loop = 0

    """
    Handlers for parallelization
    no such thing as "import parallel"!
    |/|/|/|/|/|/|/|/|/|/|/|/|/|/|/|/|/|/|/|/|/
    """

    def __getstate__(self):
        self_dict = self.__dict__.copy()
        del self_dict['Pool']
        return self_dict

    def __setstate__(self, state):
        self.__dict__.update(state)

    """
    ^^^
    Handlers for parallelization
    """

    def get_dimension(self):
        """
        Sets the dimension of the calculation. Mostly just important if you're calculating
        a slice rather than the full r, r', theta matrix.
        :return:
        """
        if self.mode == 'rrprime':
            print("Calculating r = r' slice")
            self.dimension = 2
        elif self.mode == 'rrtheta':
            print("Calculating r, r', theta slices")
            # run_rrtheta(model_padf_instance)
            pass
        elif self.mode == 'stm':
            print("Calculating Theta(r,r',theta) directly...")
            self.dimension = 3
        return self.dimension

    def write_all_params_to_file(self, name="None", script="parallel_model_padf_0p2_am.py"):
        """
        Writes all the input parameters to a log file
        :param name:
        :param script:
        :return:
        """
        if name == "None":
            f = open(self.root + self.project + self.logname, 'w')
        else:
            f = open(name, 'w')
        f.write("# log of input parameters\n")

        if script != "None":
            f.write("# generated by " + script + "\n")
        a = self.__dict__
        for d, e in a.items():
            # list of parameters to exclude
            # if d in []:
            #    print("found one", d)
            #    continue

            # write the parameter to log file
            f.write(d + " = " + str(e) + "\n")
        f.close()

    def clean_project_folder(self):
        """
        Cleans up the Theta and Theta_loop files that are generated through the calculation
        :return:
        """
        print("Cleaning work folder...")
        if self.converged_loop > 0:
            for i in range(1, int(self.converged_loop) + 1):
                os.remove(self.root + self.project + self.project[:-1] + '_Theta_loop_' + str(i) + '.npy')

            for j in range(int(self.processor_num)):
                os.remove(self.root + self.project + self.project[:-1] + '_Theta_' + str(j) + '.npy')
        else:
            for i in range(1, int(self.loops) + 2):
                os.remove(self.root + self.project + self.project[:-1] + '_Theta_loop_' + str(i) + '.npy')

            for j in range(int(self.processor_num)):
                os.remove(self.root + self.project + self.project[:-1] + '_Theta_' + str(j) + '.npy')

    def filter_subject_set(self):
        """
        Shuffles and trims the subject atoms (a.k.a. asymmetric unit) on the basis of the subject number
        in the setup file.
        Also shuffles
        :return:
        """
        print("Selecting subset of", self.subject_number, " subject atoms ")
        np.random.shuffle(self.subject_set)
        self.subject_set = self.subject_set[:self.subject_number]
        print("Subject set now includes ", len(self.subject_set), "atoms ")
        return self.subject_set

    def subject_target_setup(self):
        """
        Handlers to read in the subject atoms (a.k.a. asymmetric unit) and the extended atoms (environment)
        :return:
        """
        self.subject_set = subject_atom_reader(self.root + self.project + self.subject_atom_name,
                                               self.ucds)  # Read the full asymmetric unit
        if self.subject_number > 0:
            self.subject_set = self.filter_subject_set()  # Filter the subject set using self.subject_number
        self.raw_extended_atoms = read_xyz(
            self.root + self.project + self.xyz_name)  # Take in the raw environment atoms
        self.extended_atoms = self.clean_extended_atoms()  # Trim to the atoms probed by the subject set
        return self.subject_set, self.extended_atoms

    def sum_loop_arrays(self, loop):
        """
        Sum up the theta npy's for the loops
        up to loop
        :param loop: loop at which to perform the sum
        :return:
        """
        SumTheta = self.generate_empty_theta(self.dimension)
        if self.convergence_check_flag is False:
            for j in np.arange(1, int(loop) + 2, 1):
                chunk_Theta = np.load(self.root + self.project + self.project[:-1] + '_Theta_loop_' + str(j) + '.npy')
                SumTheta = np.add(SumTheta, chunk_Theta)
        else:
            for j in np.arange(1, int(loop) + 1, 1):
                chunk_Theta = np.load(self.root + self.project + self.project[:-1] + '_Theta_loop_' + str(j) + '.npy')
                SumTheta = np.add(SumTheta, chunk_Theta)
        if self.dimension == 2:
            np.save(self.root + self.project + self.project[:-1] + '_slice_total_sum', SumTheta)
        elif self.dimension == 3:
            np.save(self.root + self.project + self.project[:-1] + '_Theta_total_sum', SumTheta)
        return SumTheta

    def generate_empty_theta(self, shape):
        """
        Sets up the empty Theta matrix
        :return: Empty numpy array Theta
        """
        if shape == 2:
            Theta = np.zeros((int(self.r_probe / self.r_dist_bin), int(m.pi / m.radians(self.angular_bin))))
            # print("Creating empty Theta slice :", Theta.shape)
        elif shape == 3:
            Theta = np.zeros(
                (int(self.r_probe / self.r_dist_bin), int(self.r_probe / self.r_dist_bin),
                 int(m.pi / m.radians(self.angular_bin))))
        else:
            print("Please supply Theta dimension [generate_empty_theta]")
            Theta = np.zeros(0)
        # print("Creating empty Theta :", Theta.shape)
        return Theta

    def clean_extended_atoms(self):
        """
        Trims the length of the extended atoms to the set probed by
        the r_probe and asymmetric unit
        :return:
        """
        clean_ex = []
        for ex_atom in self.raw_extended_atoms:
            for as_atom in self.subject_set:
                diff = fast_vec_difmag(ex_atom[0], ex_atom[1], ex_atom[2], as_atom[0], as_atom[1], as_atom[2])
                if abs(diff) <= self.r_probe:
                    clean_ex.append(ex_atom)
                    break
                else:
                    continue
        clean_ex = np.array(clean_ex)
        print("Extended atom set has been reduced to ", len(clean_ex), " atoms within", self.r_probe, "radius ")
        return np.array(clean_ex)

    def bin_cor_vec_to_theta(self, cor_vec, array):
        """
        Bin and then add the correlation vector to the
        chunk array
        :param cor_vec: correlation vector length 2 or 3
        :param array: Theta chunk
        :return:
        """
        r_yard_stick = np.arange(self.r_dist_bin, self.r_probe + self.r_dist_bin, self.r_dist_bin)
        th_yard_stick = np.arange(0, m.pi, m.radians(self.angular_bin))
        if self.dimension == 2:
            r1_index = (np.abs(r_yard_stick - cor_vec[0])).argmin()
            th_index = (np.abs(th_yard_stick - cor_vec[-1])).argmin()
            index_vec = [r1_index, th_index]
            array[index_vec[0], index_vec[1]] += 1
        elif self.dimension == 3:
            r1_index = (np.abs(r_yard_stick - cor_vec[0])).argmin()
            r2_index = (np.abs(r_yard_stick - cor_vec[1])).argmin()
            th_index = (np.abs(th_yard_stick - cor_vec[-1])).argmin()
            array[r1_index, r2_index, th_index] += 1

    def parallel_pool_accounting(self, loop_number):
        """
        Sums arrays together for each cycle
        :param loop_number: loop id
        :return:
        """
        BigTheta = self.generate_empty_theta(self.dimension)
        for i in range(int(self.processor_num)):
            chunk_Theta = np.load(self.root + self.project + self.project[:-1] + '_Theta_' + str(i) + '.npy')
            BigTheta = np.add(BigTheta, chunk_Theta)
        np.save(self.root + self.project + self.project[:-1] + '_Theta_loop_' + str(loop_number), BigTheta)

    def prelim_padf_correction(self, raw_padf):
        if self.dimension == 2:
            th = np.outer(np.ones(raw_padf.shape[0]), np.arange(raw_padf.shape[1]))
            ith = np.where(th > 0.0)
            raw_padf[ith] *= 1.0 / np.abs(np.sin(np.pi * th[ith] / float(raw_padf.shape[1])) + 1e-3)
            r = np.outer(np.arange(raw_padf.shape[0]), np.ones(raw_padf.shape[1])) * self.r_probe / float(
                raw_padf.shape[0])
            ir = np.where(r > 1.0)
            raw_padf[ir] *= 1.0 / (r[ir] ** self.r_power)  # radial correction (edit this line [default value: **4])
            return raw_padf
        elif self.dimension == 3:
            data = np.zeros((raw_padf.shape[0], raw_padf.shape[-1]))
            for i in np.arange(
                    raw_padf.shape[0]):  # loop over NumPy array to return evenly spaced values within a given interval
                data[i, :] = raw_padf[i, i, :]
            data += data[:, ::-1]
            th = np.outer(np.ones(data.shape[0]), np.arange(data.shape[1]))
            ith = np.where(th > 0.0)
            data[ith] *= 1.0 / np.abs(np.sin(np.pi * th[ith] / float(data.shape[1])) + 1e-3)
            r = np.outer(np.arange(data.shape[0]), np.ones(data.shape[1])) * self.r_probe / float(data.shape[0])
            ir = np.where(r > 1.0)
            data[ir] *= 1.0 / (r[ir] ** self.r_power)  # radial correction (edit this line [default value: **4])
            return data

    def report_cossim(self):
        print("---------------------------------")
        print("Loop num        cosine similarity")
        print("---------------------------------")
        for i in self.loop_similarity_array:
            print(i[0], "        ", i[1])
        print("---------------------------------")

    def convergence_check(self, loop_number):
        if loop_number == 1:
            print("No convergence check in loop 1")
            return 0.0
        else:
            # calculate the n-minus_padf
            n_minus_padf = self.generate_empty_theta(self.dimension)
            for nmin_it in np.arange(1, loop_number):
                raw_loop_padf = np.load(
                    self.root + self.project + self.project[:-1] + '_Theta_loop_' + str(nmin_it) + '.npy')
                n_minus_padf = n_minus_padf + raw_loop_padf
                n_minus_padf_corr = self.prelim_padf_correction(n_minus_padf)
            # calculate the n_padf
            n_padf = self.generate_empty_theta(self.dimension)
            for n_it in np.arange(1, loop_number + 1):
                raw_loop_padf = np.load(
                    self.root + self.project + self.project[:-1] + '_Theta_loop_' + str(n_it) + '.npy')
                n_padf = n_padf + raw_loop_padf
                n_padf_corr = self.prelim_padf_correction(n_padf)
            # Normalize both arrays
            n_minus_padf_normal = n_minus_padf_corr / np.linalg.norm(n_minus_padf_corr)
            n_padf_normal = n_padf_corr / np.linalg.norm(n_padf_corr)
            loop_cos = cossim_measure(n_padf_normal, n_minus_padf_normal)
            self.loop_similarity_array.append([loop_number, loop_cos])
            self.report_cossim()
            return loop_cos

    def add_bodies_to_theta_pool(self, k, a_i):
        """
        Calculates all three- and four-body contacts and adds them to Theta
        :return:
        """
        start = time.time()
        Theta = self.generate_empty_theta(3)
        # print("Thread ", str(k), ":")
        # print("Calculating contacts and adding to Theta...")
        target_atoms = np.array(make_interaction_sphere(self.r_probe, a_i, self.extended_atoms))
        print("Thread ", str(k), ": correlation sphere contains ", len(target_atoms), "atoms")
        for a_j in target_atoms:
            for a_k in target_atoms:
                # Find vectors, differences, and angles:
                r_ij = fast_vec_difmag(a_i[0], a_i[1], a_i[2], a_j[0], a_j[1], a_j[2])
                r_ik = fast_vec_difmag(a_i[0], a_i[1], a_i[2], a_k[0], a_k[1], a_k[2])
                ij = np.array(fast_vec_subtraction(a_i[0], a_i[1], a_i[2], a_j[0], a_j[1], a_j[2]))
                ik = np.array(fast_vec_subtraction(a_i[0], a_i[1], a_i[2], a_k[0], a_k[1], a_k[2]))
                theta = fast_vec_angle(ij[0], ij[1], ij[2], ik[0], ik[1], ik[2])
                if 0.0 <= theta <= m.pi:
                    self.bin_cor_vec_to_theta([r_ij, r_ik, theta], Theta)
                else:
                    continue
                if self.fourbody:
                    k_target_atoms = np.array(make_interaction_sphere(self.r_probe, a_k, self.extended_atoms))
                    for a_m in k_target_atoms:
                        r_km = fast_vec_difmag(a_k[0], a_k[1], a_k[2], a_m[0], a_m[1], a_m[2])
                        km = np.array(fast_vec_subtraction(a_k[0], a_k[1], a_k[2], a_m[0], a_m[1], a_m[2]))
                        theta_km = fast_vec_angle(ij[0], ij[1], ij[2], km[0], km[1], km[2])
                        if 0.0 <= theta_km <= m.pi:
                            self.bin_cor_vec_to_theta([r_ij, r_km, theta_km], Theta)
                        else:
                            continue
                else:
                    continue
        end = time.time()
        print("Thread ", str(k), "execution time = ", end - start, " seconds")
        # Save the Theta array as is:
        np.save(self.root + self.project + self.project[:-1] + '_Theta_' + str(k), Theta)

    def add_bodies_to_rrprime_pool(self, k, a_i):
        """
        Calculates all three- and four-body contacts and adds them to the Theta slice
        r = r'
        :return:
        """
        start = time.time()
        Theta = self.generate_empty_theta(2)
        print("Calculating contacts and adding to Theta slice...")
        target_atoms = np.array(make_interaction_sphere(self.r_probe, a_i, self.extended_atoms))
        print("Thread ", str(k), ": correlation sphere contains ", len(target_atoms), "atoms")
        for a_j in target_atoms:
            for a_k in target_atoms:
                # Find vectors, differences, and angles:
                r_ij = fast_vec_difmag(a_i[0], a_i[1], a_i[2], a_j[0], a_j[1], a_j[2])
                r_ik = fast_vec_difmag(a_i[0], a_i[1], a_i[2], a_k[0], a_k[1], a_k[2])
                diff = abs(r_ij - r_ik)
                if diff < self.r_dist_bin:
                    ij = np.array(fast_vec_subtraction(a_i[0], a_i[1], a_i[2], a_j[0], a_j[1], a_j[2]))
                    ik = np.array(fast_vec_subtraction(a_i[0], a_i[1], a_i[2], a_k[0], a_k[1], a_k[2]))
                    theta = fast_vec_angle(ij[0], ij[1], ij[2], ik[0], ik[1], ik[2])
                    if 0.0 <= theta <= m.pi:
                        self.bin_cor_vec_to_theta([r_ij, theta], Theta)
                    else:
                        continue
                else:
                    continue
                if self.fourbody:
                    k_target_atoms = np.array(make_interaction_sphere(self.r_probe, a_k, self.extended_atoms))
                    for a_m in k_target_atoms:
                        r_km = fast_vec_difmag(a_k[0], a_k[1], a_k[2], a_m[0], a_m[1], a_m[2])
                        diff_k = abs(r_ij - r_km)
                        if diff_k < self.r_dist_bin:
                            km = np.array(fast_vec_subtraction(a_k[0], a_k[1], a_k[2], a_m[0], a_m[1], a_m[2]))
                            theta_km = fast_vec_angle(ij[0], ij[1], ij[2], km[0], km[1], km[2])
                            if 0.0 <= theta_km <= m.pi:
                                self.bin_cor_vec_to_theta([r_ij, theta_km], Theta)
                            else:
                                continue
                else:
                    continue
        end = time.time()
        print("Thread ", str(k), "execution time = ", end - start, " seconds")
        # Save the Theta array as is:
        np.save(self.root + self.project + self.project[:-1] + '_Theta_' + str(k), Theta)

    def run(self):
        """
        Runs the Straight-To-Matrix model PADF calculation
        :return:
        """
        start = time.time()
        self.subject_set, self.extended_atoms = self.subject_target_setup()
        self.dimension = self.get_dimension()
        """
        Here we do the chunking for sending to threads
        """
        np.random.shuffle(self.subject_set)  # Shuffle the asymmetric unit
        self.loops = int(len(self.subject_set) / self.processor_num)  # The number of loops for complete calculation
        # chunked add_bodies_to_theta:
        for loop_id in np.arange(1, int(self.loops) + 2, 1):
            print(str(loop_id) + " / " + str(int(self.loops) + 1))
            cluster_asymm = self.subject_set[
                            (
                                    loop_id - 1) * self.processor_num:loop_id * self.processor_num]  # Create a chunk of to send out
            if self.mode == 'rrprime':
                processes = [mp.Process(target=self.add_bodies_to_rrprime_pool, args=(i, cl_atom)) for i, cl_atom in
                             enumerate(cluster_asymm)]
            elif self.mode == 'stm':
                processes = [mp.Process(target=self.add_bodies_to_theta_pool, args=(i, cl_atom)) for i, cl_atom in
                             enumerate(cluster_asymm)]
            else:
                print("ERROR: Missing mode")
                break
            for p in processes:
                p.start()
            for p in processes:
                p.join()
            # Crunch the npy arrays together for this loop
            self.parallel_pool_accounting(loop_id)

            # Check for convergence if required
            if self.convergence_check_flag:
                loop_convergence = self.convergence_check(loop_id)
                if loop_convergence >= self.convergence_target:
                    print("Calculation converged at loop ", loop_id)
                    self.converged_loop = loop_id
                    break

        # Crunch the npy arrays together for all loops:
        if self.convergence_check_flag:
            print("converged_loop: ", self.converged_loop)
            BigTheta = self.sum_loop_arrays(loop=self.converged_loop)
        else:
            BigTheta = self.sum_loop_arrays(loop=self.loops)
        end = time.time()
        # Check to see if the folder should be cleaned
        if self.verbosity == 0:
            self.clean_project_folder()
        print("Total run time = ", end - start, " seconds")
        if self.dimension == 2:
            plt.imshow(BigTheta)
            plt.show()


if __name__ == '__main__':
    modelp = ModelPADF()
    modelp.write_all_params_to_file()
