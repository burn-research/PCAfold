"""analysis.py: module for manifolds analysis."""

__author__ = "Kamila Zdybal, Elizabeth Armstrong, Alessandro Parente and James C. Sutherland"
__copyright__ = "Copyright (c) 2020, 2021, Kamila Zdybal, Elizabeth Armstrong, Alessandro Parente and James C. Sutherland"
__credits__ = ["Department of Chemical Engineering, University of Utah, Salt Lake City, Utah, USA", "Universite Libre de Bruxelles, Aero-Thermo-Mechanics Laboratory, Brussels, Belgium"]
__license__ = "MIT"
__version__ = "1.0.0"
__maintainer__ = ["Kamila Zdybal", "Elizabeth Armstrong"]
__email__ = ["kamilazdybal@gmail.com", "Elizabeth.Armstrong@chemeng.utah.edu", "James.Sutherland@chemeng.utah.edu"]
__status__ = "Production"

import numpy as np
import copy as cp
import multiprocessing as multiproc
from PCAfold import KReg
from scipy.spatial import KDTree
from scipy.optimize import minimize
from scipy.signal import find_peaks
import matplotlib.pyplot as plt
import random as rnd
from scipy.interpolate import CubicSpline
from PCAfold.styles import *
from PCAfold import preprocess
from PCAfold import reduction
from termcolor import colored
import time

################################################################################
#
# Manifold assessment
#
################################################################################

class VarianceData:
    """
    A class for storing helpful quantities in analyzing dimensionality of manifolds through normalized variance measures.
    This class will be returned by ``compute_normalized_variance``.

    :param bandwidth_values:
        the array of bandwidth values (Gaussian filter widths) used in computing the normalized variance for each variable
    :param normalized_variance:
        dictionary of the normalized variance computed at each of the bandwidth values for each variable
    :param global_variance:
        dictionary of the global variance for each variable
    :param bandwidth_10pct_rise:
        dictionary of the bandwidth value corresponding to a 10% rise in the normalized variance for each variable
    :param variable_names:
        list of the variable names
    :param normalized_variance_limit:
        dictionary of the normalized variance computed as the bandwidth approaches zero (numerically at :math:`10^{-16}`) for each variable
    """

    def __init__(self, bandwidth_values, norm_var, global_var, bandwidth_10pct_rise, keys, norm_var_limit):
        self._bandwidth_values = bandwidth_values.copy()
        self._normalized_variance = norm_var.copy()
        self._global_variance = global_var.copy()
        self._bandwidth_10pct_rise = bandwidth_10pct_rise.copy()
        self._variable_names = keys.copy()
        self._normalized_variance_limit = norm_var_limit.copy()

    @property
    def bandwidth_values(self):
        """return the bandwidth values (Gaussian filter widths) used in computing the normalized variance for each variable"""
        return self._bandwidth_values.copy()

    @property
    def normalized_variance(self):
        """return a dictionary of the normalized variance computed at each of the bandwidth values for each variable"""
        return self._normalized_variance.copy()

    @property
    def global_variance(self):
        """return a dictionary of the global variance for each variable"""
        return self._global_variance.copy()

    @property
    def bandwidth_10pct_rise(self):
        """return a dictionary of the bandwidth value corresponding to a 10% rise in the normalized variance for each variable"""
        return self._bandwidth_10pct_rise.copy()

    @property
    def variable_names(self):
        """return a list of the variable names"""
        return self._variable_names.copy()

    @property
    def normalized_variance_limit(self):
        """return a dictionary of the normalized variance computed as the
        bandwidth approaches zero (numerically at 1.e-16) for each variable"""
        return self._normalized_variance_limit.copy()

# ------------------------------------------------------------------------------

def compute_normalized_variance(indepvars, depvars, depvar_names, npts_bandwidth=25, min_bandwidth=None,
                                max_bandwidth=None, bandwidth_values=None, scale_unit_box=True, n_threads=None):
    """
    Compute a normalized variance (and related quantities) for analyzing manifold dimensionality.
    The normalized variance is computed as

    .. math::

        \\mathcal{N}(\\sigma) = \\frac{\\sum_{i=1}^n (y_i - \\mathcal{K}(\\hat{x}_i; \\sigma))^2}{\\sum_{i=1}^n (y_i - \\bar{y} )^2}

    where :math:`\\bar{y}` is the average quantity over the whole manifold and :math:`\\mathcal{K}(\\hat{x}_i; \\sigma)` is the
    weighted average quantity calculated using kernel regression with a Gaussian kernel of bandwidth :math:`\\sigma` centered
    around the :math:`i^{th}` observation. :math:`n` is the number of observations.
    :math:`\\mathcal{N}(\\sigma)` is computed for each bandwidth in an array of bandwidth values.
    By default, the ``indepvars`` (:math:`x`) are centered and scaled to reside inside a unit box (resulting in :math:`\\hat{x}`) so that the bandwidths have the
    same meaning in each dimension. Therefore, the bandwidth and its involved calculations are applied in the normalized
    independent variable space. This may be turned off by setting ``scale_unit_box`` to False.
    The bandwidth values may be specified directly through ``bandwidth_values`` or default values will be calculated as a
    logspace from ``min_bandwidth`` to ``max_bandwidth`` with ``npts_bandwidth`` number of values. If left unspecified,
    ``min_bandwidth`` and ``max_bandwidth`` will be calculated as the minimum and maximum nonzero distance between points, respectively.

    More information can be found in :cite:`Armstrong2021`.

    **Example:**

    .. code:: python

        from PCAfold import PCA, compute_normalized_variance
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,5)

        # Perform PCA to obtain the low-dimensional manifold:
        pca_X = PCA(X, n_components=2)
        principal_components = pca_X.transform(X)

        # Compute normalized variance quantities:
        variance_data = compute_normalized_variance(principal_components, X, depvar_names=['A', 'B', 'C', 'D', 'E'], bandwidth_values=np.logspace(-3, 1, 20), scale_unit_box=True)

        # Access bandwidth values:
        variance_data.bandwidth_values

        # Access normalized variance values:
        variance_data.normalized_variance

        # Access normalized variance values for a specific variable:
        variance_data.normalized_variance['B']

    :param indepvars:
        ``numpy.ndarray`` specifying the independent variable values. It should be of size ``(n_observations,n_independent_variables)``.
    :param depvars:
        ``numpy.ndarray`` specifying the dependent variable values. It should be of size ``(n_observations,n_dependent_variables)``.
    :param depvar_names:
        ``list`` of ``str`` corresponding to the names of the dependent variables (for saving values in a dictionary)
    :param npts_bandwidth:
        (optional, default 25) number of points to build a logspace of bandwidth values
    :param min_bandwidth:
        (optional, default to minimum nonzero interpoint distance) minimum bandwidth
    :param max_bandwidth:
        (optional, default to estimated maximum interpoint distance) maximum bandwidth
    :param bandwidth_values:
        (optional) array of bandwidth values, i.e. filter widths for a Gaussian filter, to loop over
    :param scale_unit_box:
        (optional, default True) center/scale the independent variables between [0,1] for computing a normalized variance so the bandwidth values have the same meaning in each dimension
    :param n_threads:
        (optional, default None) number of threads to run this computation. If None, default behavior of multiprocessing.Pool is used, which is to use all available cores on the current system.

    :return:
        a ``VarianceData`` class
    """
    assert indepvars.ndim == 2, "independent variable array must be 2D: n_observations x n_variables."
    assert depvars.ndim == 2, "dependent variable array must be 2D: n_observations x n_variables."
    assert (indepvars.shape[0] == depvars.shape[
        0]), "The number of observations for dependent and independent variables must match."
    assert (len(depvar_names) == depvars.shape[
        1]), "The provided keys do not match the shape of the dependent variables yi."

    if scale_unit_box:
        xi = (indepvars - np.min(indepvars, axis=0)) / (np.max(indepvars, axis=0) - np.min(indepvars, axis=0))
    else:
        xi = indepvars.copy()

    yi = depvars.copy()

    if bandwidth_values is None:
        if min_bandwidth is None:
            tree = KDTree(xi)
            min_bandwidth = np.min(tree.query(xi, k=2)[0][tree.query(xi, k=2)[0][:, 1] > 1.e-16, 1])
        if max_bandwidth is None:
            max_bandwidth = np.linalg.norm(np.max(xi, axis=0) - np.min(xi, axis=0)) * 10.
        bandwidth_values = np.logspace(np.log10(min_bandwidth), np.log10(max_bandwidth), npts_bandwidth)
    else:
        if not isinstance(bandwidth_values, np.ndarray):
            raise ValueError("bandwidth_values must be an array.")

    lvar = np.zeros((bandwidth_values.size, yi.shape[1]))
    kregmod = KReg(xi, yi)  # class for kernel regression evaluations

    # define a list of argments for kregmod_predict
    fcnArgs = [(xi, bandwidth_values[si]) for si in range(bandwidth_values.size) ]

    pool = multiproc.Pool(processes=n_threads)
    kregmodResults = pool.starmap( kregmod.predict, fcnArgs)

    pool.close()
    pool.join()

    for si in range(bandwidth_values.size):
        lvar[si, :] = np.linalg.norm(yi - kregmodResults[si], axis=0) ** 2

    # saving the local variance for each yi...
    local_var = dict({key: lvar[:, idx] for idx, key in enumerate(depvar_names)})
    # saving the global variance for each yi...
    global_var = dict(
        {key: np.linalg.norm(yi[:, idx] - np.mean(yi[:, idx])) ** 2 for idx, key in enumerate(depvar_names)})
    # saving the values of the bandwidth where the normalized variance increases by 10%...
    bandwidth_10pct_rise = dict()
    for key in depvar_names:
        bandwidth_idx = np.argwhere(local_var[key] / global_var[key] >= 0.1)
        if len(bandwidth_idx) == 0.:
            bandwidth_10pct_rise[key] = None
        else:
            bandwidth_10pct_rise[key] = bandwidth_values[bandwidth_idx[0]][0]
    norm_local_var = dict({key: local_var[key] / global_var[key] for key in depvar_names})

    # computing normalized variance as bandwidth approaches zero to check for non-uniqueness
    lvar_limit = kregmod.predict(xi, 1.e-16)
    nlvar_limit = np.linalg.norm(yi - lvar_limit, axis=0) ** 2
    normvar_limit = dict({key: nlvar_limit[idx] for idx, key in enumerate(depvar_names)})

    solution_data = VarianceData(bandwidth_values, norm_local_var, global_var, bandwidth_10pct_rise, depvar_names, normvar_limit)
    return solution_data

# ------------------------------------------------------------------------------

def normalized_variance_derivative(variance_data):
    """
    Compute a scaled normalized variance derivative on a logarithmic scale, :math:`\\hat{\\mathcal{D}}(\\sigma)`, from

    .. math::

        \\mathcal{D}(\\sigma) = \\frac{\\mathrm{d}\\mathcal{N}(\\sigma)}{\\mathrm{d}\\log_{10}(\\sigma)} + \lim_{\\sigma \\to 0} \\mathcal{N}(\\sigma)

    and

    .. math::

        \\hat{\\mathcal{D}}(\\sigma) = \\frac{\\mathcal{D}(\\sigma)}{\\max(\\mathcal{D}(\\sigma))}

    This value relays how fast the variance is changing as the bandwidth changes and captures non-uniqueness from
    nonzero values of :math:`\lim_{\\sigma \\to 0} \\mathcal{N}(\\sigma)`. The derivative is approximated
    with central finite differencing and the limit is approximated by :math:`\\mathcal{N}(\\sigma=10^{-16})` using the
    ``normalized_variance_limit`` attribute of the ``VarianceData`` object.

    More information can be found in :cite:`Armstrong2021`.

    :param variance_data:
        a ``VarianceData`` class returned from ``compute_normalized_variance``

    :return:
        - a dictionary of :math:`\\hat{\\mathcal{D}}(\\sigma)` for each variable in the provided ``VarianceData`` object
        - the :math:`\\sigma` values where :math:`\\hat{\\mathcal{D}}(\\sigma)` was computed
        - a dictionary of :math:`\\max(\\mathcal{D}(\\sigma))` values for each variable in the provided ``VarianceData`` object.
    """
    x_plus = variance_data.bandwidth_values[2:]
    x_minus = variance_data.bandwidth_values[:-2]
    x = variance_data.bandwidth_values[1:-1]
    derivative_dict = {}
    max_derivatives_dict = {}
    for key in variance_data.variable_names:
        y_plus = variance_data.normalized_variance[key][2:]
        y_minus = variance_data.normalized_variance[key][:-2]
        derivative = (y_plus-y_minus)/(np.log10(x_plus)-np.log10(x_minus)) + variance_data.normalized_variance_limit[key]
        scaled_derivative = derivative/np.max(derivative)
        derivative_dict[key] = scaled_derivative
        max_derivatives_dict[key] = np.max(derivative)
    return derivative_dict, x, max_derivatives_dict

# ------------------------------------------------------------------------------

def find_local_maxima(dependent_values, independent_values, logscaling=True, threshold=1.e-2, show_plot=False):
    """
    Finds and returns locations and values of local maxima in a dependent variable given a set of observations.
    The functional form of the dependent variable is approximated with a cubic spline for smoother approximations to local maxima.

    :param dependent_values:
        observations of a single dependent variable such as :math:`\\hat{\\mathcal{D}}` from ``normalized_variance_derivative`` (for a single variable).
    :param independent_values:
        observations of a single independent variable such as :math:`\\sigma` returned by ``normalized_variance_derivative``
    :param logscaling:
        (optional, default True) this logarithmically scales ``independent_values`` before finding local maxima. This is needed for scaling :math:`\\sigma` appropriately before finding peaks in :math:`\\hat{\\mathcal{D}}`.
    :param threshold:
        (optional, default :math:`10^{-2}`) local maxima found below this threshold will be ignored.
    :param show_plot:
        (optional, default False) when True, a plot of the ``dependent_values`` over ``independent_values`` (logarithmically scaled if ``logscaling`` is True) with the local maxima highlighted will be shown.

    :return:
        - the locations of local maxima in ``dependent_values``
        - the local maxima values
    """
    if logscaling:
        independent_values = np.log10(independent_values.copy())
    zero_indices = []
    upslope = True
    npts = independent_values.size
    for i in range(1, npts):
        if upslope and dependent_values[i] - dependent_values[i - 1] <= 0:
            if dependent_values[i] > threshold:
                zero_indices.append(i - 1)
            upslope = False
        if not upslope and dependent_values[i] - dependent_values[i - 1] >= 0:
            upslope = True

    zero_locations = []
    zero_Dvalues = []
    for idx in zero_indices:
        if idx < 1:
            indices = [idx, idx + 1, idx + 2, idx + 3]
        elif idx < 2:
            indices = [idx - 1, idx, idx + 1, idx + 2]
        elif idx > npts - 1:
            indices = [idx - 3, idx - 2, idx - 1, idx]
        else:
            indices = [idx - 2, idx - 1, idx, idx + 1]
        Dspl = CubicSpline(independent_values[indices], dependent_values[indices])
        sigma_max = minimize(lambda s: -Dspl(s), independent_values[idx])
        zero_locations.append(sigma_max.x[0])
        zero_Dvalues.append(Dspl(sigma_max.x[0]))
    if show_plot:
        plt.plot(independent_values, dependent_values, 'k-')
        plt.plot(zero_locations, zero_Dvalues, 'r*')
        plt.xlim([np.min(independent_values),np.max(independent_values)])
        plt.ylim([0., 1.05])
        plt.grid()
        if logscaling:
            plt.xlabel('log$_{10}$(independent variable)')
        else:
            plt.xlabel('independent variable')
        plt.ylabel('dependent variable')
        plt.show()
    if logscaling:
        zero_locations = 10. ** np.array(zero_locations)
    return np.array(zero_locations, dtype=float), np.array(zero_Dvalues, dtype=float)

# ------------------------------------------------------------------------------

def random_sampling_normalized_variance(sampling_percentages, indepvars, depvars, depvar_names,
                                        n_sample_iterations=1, verbose=True, npts_bandwidth=25, min_bandwidth=None,
                                        max_bandwidth=None, bandwidth_values=None, scale_unit_box=True, n_threads=None):
    """
    Compute the normalized variance derivatives :math:`\\hat{\\mathcal{D}}(\\sigma)` for random samples of the provided
    data specified using ``sampling_percentages``. These will be averaged over ``n_sample_iterations`` iterations. Analyzing
    the shift in peaks of :math:`\\hat{\\mathcal{D}}(\\sigma)` due to sampling can distinguish between characteristic
    features and non-uniqueness due to a transformation/reduction of manifold coordinates. True features should not show
    significant sensitivity to sampling while non-uniqueness/folds in the manifold will.

    More information can be found in :cite:`Armstrong2021`.

    :param sampling_percentages:
        list or 1D array of fractions (between 0 and 1) of the provided data to sample for computing the normalized variance
    :param indepvars:
        independent variable values (size: n_observations x n_independent variables)
    :param depvars:
        dependent variable values (size: n_observations x n_dependent variables)
    :param depvar_names:
        list of strings corresponding to the names of the dependent variables (for saving values in a dictionary)
    :param n_sample_iterations:
        (optional, default 1) how many iterations for each ``sampling_percentages`` to average the normalized variance derivative over
    :param verbose:
        (optional, default True) when True, progress statements are printed
    :param npts_bandwidth:
        (optional, default 25) number of points to build a logspace of bandwidth values
    :param min_bandwidth:
        (optional, default to minimum nonzero interpoint distance) minimum bandwidth
    :param max_bandwidth:
        (optional, default to estimated maximum interpoint distance) maximum bandwidth
    :param bandwidth_values:
        (optional) array of bandwidth values, i.e. filter widths for a Gaussian filter, to loop over
    :param scale_unit_box:
        (optional, default True) center/scale the independent variables between [0,1] for computing a normalized variance so the bandwidth values have the same meaning in each dimension
    :param n_threads:
        (optional, default None) number of threads to run this computation. If None, default behavior of multiprocessing.Pool is used, which is to use all available cores on the current system.

    :return:
        - a dictionary of the normalized variance derivative (:math:`\\hat{\\mathcal{D}}(\\sigma)`) for each sampling percentage in ``sampling_percentages`` averaged over ``n_sample_iterations`` iterations
        - the :math:`\\sigma` values used for computing :math:`\\hat{\\mathcal{D}}(\\sigma)`
        - a dictionary of the ``VarianceData`` objects for each sampling percentage and iteration in ``sampling_percentages`` and ``n_sample_iterations``
    """
    assert indepvars.ndim == 2, "independent variable array must be 2D: n_observations x n_variables."
    assert depvars.ndim == 2, "dependent variable array must be 2D: n_observations x n_variables."

    if isinstance(sampling_percentages, list):
        for p in sampling_percentages:
            assert p > 0., "sampling percentages must be between 0 and 1"
            assert p <= 1., "sampling percentages must be between 0 and 1"
    elif isinstance(sampling_percentages, np.ndarray):
        assert sampling_percentages.ndim ==1, "sampling_percentages must be given as a list or 1D array"
        for p in sampling_percentages:
            assert p > 0., "sampling percentages must be between 0 and 1"
            assert p <= 1., "sampling percentages must be between 0 and 1"
    else:
        raise ValueError("sampling_percentages must be given as a list or 1D array.")

    normvar_data = {}
    avg_der_data = {}

    for p in sampling_percentages:
        if verbose:
            print('sampling', p * 100., '% of the data')
        nv_data = {}
        avg_der = {}

        for it in range(n_sample_iterations):
            if verbose:
                print('  iteration', it + 1, 'of', n_sample_iterations)
            rnd.seed(it)
            idxsample = rnd.sample(list(np.arange(0, indepvars.shape[0])), int(p * indepvars.shape[0]))
            nv_data[it] = compute_normalized_variance(indepvars[idxsample, :], depvars[idxsample, :], depvar_names,
                                                      npts_bandwidth=npts_bandwidth, min_bandwidth=min_bandwidth,
                                                      max_bandwidth=max_bandwidth, bandwidth_values=bandwidth_values,
                                                      scale_unit_box=scale_unit_box, n_threads=n_threads)

            der, xder, _ = normalized_variance_derivative(nv_data[it])
            for key in der.keys():
                if it == 0:
                    avg_der[key] = der[key] / np.float(n_sample_iterations)
                else:
                    avg_der[key] += der[key] / np.float(n_sample_iterations)

        avg_der_data[p] = avg_der
        normvar_data[p] = nv_data
    return avg_der_data, xder, normvar_data

# ------------------------------------------------------------------------------

def average_knn_distance(indepvars, n_neighbors=10, verbose=False):
    """
    Computes average Euclidean distances to :math:`k` nearest neighbors on
    a manifold defined by the independent variables.

    **Example:**

    .. code:: python

        from PCAfold import PCA, average_knn_distance
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,20)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='none', n_components=2, use_eigendec=True, nocenter=False)

        # Calculate the principal components:
        principal_components = pca_X.transform(X)

        # Compute average distances on a manifold defined by the PCs:
        average_distances = average_knn_distance(principal_components, n_neighbors=10, verbose=True)

    With ``verbose=True``, minimum, maximum and average distance will be printed:

    .. code-block:: text

        Minimum distance:	0.09949245121415481
        Maximum distance:	0.5479877680240044
        Average distance:	0.21458565264098528

    :param indepvars:
        ``numpy.ndarray`` specifying the independent variable values. It should be of size ``(n_observations,n_independent_variables)``.
    :param n_neighbors: (optional)
        ``int`` specifying the number of nearest neighbors, :math:`k`.
    :param verbose: (optional)
        ``bool`` for printing verbose details.

    :return:
        - **average_distances** - ``numpy.ndarray`` specifying the vector of average distances for every observation in a data set to its :math:`k` nearest neighbors. It has size ``(n_observations,)``.
    """

    if not isinstance(indepvars, np.ndarray):
        raise ValueError("Parameter `indepvars` has to be of type `numpy.ndarray`.")

    try:
        (n_observations, n_independent_variables) = np.shape(indepvars)
    except:
        raise ValueError("Parameter `indepvars` has to have size `(n_observations,n_independent_variables)`.")

    if not isinstance(n_neighbors, int):
        raise ValueError("Parameter `n_neighbors` has to be of type int.")

    if n_neighbors < 2:
        raise ValueError("Parameter `n_neighbors` cannot be smaller than 2.")

    if not isinstance(verbose, bool):
        raise ValueError("Parameter `verbose` has to be a boolean.")

    try:
        from sklearn.neighbors import NearestNeighbors
    except:
        raise ValueError("Nearest neighbors search requires the `sklearn` module: `pip install sklearn`.")

    (n_observations, n_independent_variables) = np.shape(indepvars)

    knn_model = NearestNeighbors(n_neighbors=n_neighbors+1)
    knn_model.fit(indepvars)

    average_distances = np.zeros((n_observations,))

    for query_point in range(0,n_observations):

        (distances_neigh, idx_neigh) = knn_model.kneighbors(indepvars[query_point,:][None,:], n_neighbors=n_neighbors+1, return_distance=True)
        query_point_idx = np.where(idx_neigh.ravel()==query_point)
        distances_neigh = np.delete(distances_neigh.ravel(), np.s_[query_point_idx])
        idx_neigh = np.delete(idx_neigh.ravel(), np.s_[query_point_idx])
        average_distances[query_point] = np.mean(distances_neigh)

    if verbose:
        print('Minimum distance:\t' + str(np.min(average_distances)))
        print('Maximum distance:\t' + str(np.max(average_distances)))
        print('Average distance:\t' + str(np.mean(average_distances)))

    return average_distances

# ------------------------------------------------------------------------------

def cost_function_normalized_variance_derivative(variance_data, weight_area=False, direct_integration=True):
    """
    Defines a cost function for manifold optimization algorithms based on the average area under
    the normalized variance derivatives, :math:`\\hat{\\mathcal{D}}(\\sigma)`, for the selected :math:`n_{dep}` dependent variables.
    The area is computed in the :math:`\\log_{10}` space of bandwidths :math:`\\sigma`.

    Two choices for the individual area computation can be made:

    - If ``direct_integration=True``, the area is computed by directly \
    integrating the function :math:`\\hat{\\mathcal{D}}(\\sigma)``. Integration \
    is performed using the composite trapezoid rule. An individual area \
    for the :math:`i^{th}` dependent variable is then defined as:

    .. math::

        A_i = \\int_{\\sigma_{min, i}}^{\\sigma_{peak, i}} \\hat{\\mathcal{D}}_i(\\sigma) d \\log_{10} \\sigma

    - If ``direct_integration=False``, we use the fact that :math:`\\hat{\\mathcal{D}}(\\sigma)`` \
    is a numerical derivative of :math:`\\mathcal{N}(\\sigma)`. An individual area \
    for the :math:`i^{th}` dependent variable is then defined as:

    .. math::

        A_i = \\frac{\\mathcal{N}_i(\\sigma_{peak, i}) - \\mathcal{N}_i(\\sigma_{min, i})}{\\max(\\mathcal{D}_i(\\sigma))}  + \\frac{\\lim_{\\sigma \\rightarrow 0} \\mathcal{N_i(\\sigma)}}{\\max(\\mathcal{D}_i(\\sigma))}  \\big( \\log_{10} \\sigma_{peak, i} - \\log_{10} \\sigma_{min, i} \\big)

    The cost, :math:`E`, can then be computed from all :math:`A_i` in two ways,
    where :math:`n_{dep}` is the number of dependent variables stored in the ``variance_data`` object:

    - If ``weight_area=False``:

    .. math::

        E = \\frac{1}{n_{dep}} \\sum_{i = 1}^{n_{dep}} A_i

    - If ``weight_area=True``, each area is additionally weighted by the location \
    of the rightmost peak, :math:`\\sigma_{peak, i}`, in :math:`\\hat{\\mathcal{D}}_i(\\sigma)``:

    .. math::

        E = \\frac{1}{n_{dep}} \\sum_{i = 1}^{n_{dep}} \\frac{1}{\\sigma_{peak, i}} A_i

    :param variance_data:
        an object of ``VarianceData`` class.
    :param weight_area: (optional)
        ``bool`` specifying whether each computed area should be weighted by the rightmost peak location, :math:`\\sigma_{peak, i}` for the :math:`i^{th}` dependent variable.
    :param direct_integration: (optional)
        ``bool`` specifying whether an individual area for the :math:`i^{th}` dependent variable should be computed by direct integration of the :math:`\\hat{\\mathcal{D}}(\\sigma)` curve.

    :return:
        - **cost** - ``float`` specifying the cost, :math:`E`.
    """

    if not isinstance(weight_area, bool):
        raise ValueError("Parameter `weight_area` has to be of type `bool`.")

    if not isinstance(direct_integration, bool):
        raise ValueError("Parameter `direct_integration` has to be of type `bool`.")

    # Compute the area by direct integration: ----------------------------------
    if direct_integration:

        derivative, sigma, _ = normalized_variance_derivative(variance_data)

        areas = []
        weight = 1.

        n_variables = 0

        for variable in variance_data.variable_names:
            n_variables += 1
            idx_peaks, _ = find_peaks(derivative[variable], height=0)
            peak_locations = sigma[idx_peaks]
            peak_location = peak_locations[-1]

            if weight_area:
                weight = 1. / (peak_location)

            (indices_to_the_left_of_peak, ) = np.where(sigma<=peak_location)
            areas.append(weight * np.trapz(derivative[variable][indices_to_the_left_of_peak], np.log10(sigma[indices_to_the_left_of_peak])))

        cost = np.sum(areas) / len(areas)

    # Computed the area from the normalized variance: --------------------------
    else:

        derivative, sigma, max_derivatives = normalized_variance_derivative(variance_data)
        normalized_variance_limit_dict = variance_data.normalized_variance_limit
        normalized_variance = variance_data.normalized_variance

        areas = []
        weight = 1.

        n_variables = 0

        for variable in variance_data.variable_names:
            n_variables += 1
            idx_peaks, _ = find_peaks(derivative[variable], height=0)
            peak_locations = sigma[idx_peaks]
            peak_location = peak_locations[-1]

            if weight_area:
                weight = 1. / (sigma_peak)

            sigma_min = np.min(sigma)

            N_at_peak = np.interp(sigma_peak, variance_data.bandwidth_values, variance_data.normalized_variance[variable])
            N_at_min = np.interp(sigma_min, variance_data.bandwidth_values, variance_data.normalized_variance[variable])

            TERM_1 = (1. / max_derivatives[variable]) * (N_at_peak - N_at_min)
            TERM_2 = (normalized_variance_limit_dict[variable])/(max_derivatives[variable]) * (np.log10(sigma_peak) - np.log10(sigma_min))
            area = TERM_1 + TERM_2

            areas.append(weight * area)

        cost = np.sum(areas) / len(areas)

    return cost

# ------------------------------------------------------------------------------

def manifold_informed_feature_selection(X, X_source, variable_names, scaling, bandwidth_values, d_hat_variables=None, target_manifold_dimensionality=3, bootstrap_variables=None, weight_area=False, direct_integration=False, verbose=False):
    """
    Manifold-informed feature selection algorithm.

    :param X:
        ``numpy.ndarray`` specifying the original data set, :math:`\mathbf{X}`. It should be of size ``(n_observations,n_variables)``.
    :param X_source:
        ``numpy.ndarray`` specifying the source terms, :math:`\mathbf{S_X}`, corresponding to the state-space
        variables in :math:`\mathbf{X}`. This parameter is applicable to data sets
        representing reactive flows. More information can be found in :cite:`Sutherland2009`.
    :param variable_names:
        ``list`` of ``str`` specifying variable names.
    :param scaling: (optional)
        ``str`` specifying the scaling methodology. It can be one of the following:
        ``'none'``, ``''``, ``'auto'``, ``'std'``, ``'pareto'``, ``'vast'``, ``'range'``, ``'0to1'``,
        ``'-1to1'``, ``'level'``, ``'max'``, ``'poisson'``, ``'vast_2'``, ``'vast_3'``, ``'vast_4'``.
    :param bandwidth_values:
        ``numpy.ndarray`` specifying the bandwidth values, :math:`\\sigma`, for :math:`\\hat{\\mathcal{D}}(\\sigma)` computation.
    :param d_hat_variables:
        ``list`` specifying which state variables should be used in :math:`\\hat{\\mathcal{D}}(\\sigma)` computation. If set to ``None``, only the PC source terms are used in :math:`\\hat{\\mathcal{D}}(\\sigma)` computation.
    :param target_manifold_dimensionality: (optional)
        ``int`` specifying the target dimensionality of the PCA manifold.
    :param bootstrap_variables: (optional)
        ``list`` specifying the user-selected variables to bootstrap the algorithm with. If set to ``None``, automatic bootstrapping is performed.
    :param weight_area: (optional)
        ``bool`` specifying whether each computed area should be weighted by the rightmost peak location, :math:`\\sigma_{peak, i}` for the :math:`i^{th}` dependent variable.
    :param direct_integration: (optional)
        ``bool`` specifying whether an individual area for the :math:`i^{th}` dependent variable should be computed by direct integration of the :math:`\\hat{\\mathcal{D}}(\\sigma)`` curve.
    :param verbose: (optional)
        ``bool`` for printing verbose details.

    :return:
        - **selected_variables** - ``list`` specifying the indices of the selected variables (features).
    """

    (n_observations, n_variables) = np.shape(X)

    variables_indices = [i for i in range(0,n_variables)]

    # Automatic bootstrapping: -------------------------------------------------
    if bootstrap_variables is None:

        if verbose: print('Automatic bootstrapping...\n')

        bootstrap_cost_function = []

        for i_variable in variables_indices:

            bootstrap_tic = time.perf_counter()

            if verbose: print('\tCurrently checking variable:\t' + variable_names[i_variable])

            # bootstrap_pca = reduction.PCA(X[:,[i_variable]], scaling=scaling, n_components=1)
            # PCs = bootstrap_pca.transform(X[:,[i_variable]])
            # PC_sources = bootstrap_pca.transform(X_source[:,[i_variable]], nocenter=True)

            PCs = X[:,[i_variable]]
            PC_sources = X_source[:,[i_variable]]

            if d_hat_variables is not None:
                depvars = np.hstack((PC_sources, X[:,d_hat_variables]))
                depvar_names = ['SZ1'] + list(variable_names[d_hat_variables])
            else:
                depvars = cp.deepcopy(PC_sources)
                depvar_names = ['SZ1']

            bootstrap_variance_data = compute_normalized_variance(PCs, depvars, depvar_names=depvar_names, bandwidth_values=bandwidth_values)

            bootstrap_area = cost_function_normalized_variance_derivative(bootstrap_variance_data, weight_area=weight_area, direct_integration=direct_integration)
            if verbose: print('\tCost area:\t%.4f' % bootstrap_area)
            bootstrap_cost_function.append(bootstrap_area)

        # Find a single best variable to bootstrap with:
        (best_bootstrap_variable_index, ) = np.where(np.array(bootstrap_cost_function)==np.min(bootstrap_cost_function))
        best_bootstrap_variable_index = int(best_bootstrap_variable_index)

        bootstrap_variables = [best_bootstrap_variable_index]

        if verbose: print('\nVariable ' + variable_names[best_bootstrap_variable_index] + ' will be used as bootstrap.')

        bootstrap_toc = time.perf_counter()
        if verbose: print(f'\nBoostrapping time: {(bootstrap_toc - bootstrap_tic)/60:0.1f} minutes.' + '\n' + '-'*50)

    # Use user-defined bootstrapping: ------------------------------------------
    else:

        # Manifold dimensionality needs a fix here!
        if verbose: print('User-defined bootstrapping...\n')

        bootstrap_cost_function = []

        bootstrap_tic = time.perf_counter()

        if len(bootstrap_variables) < target_manifold_dimensionality:
            n_components = len(bootstrap_variables)
        else:
            n_components = cp.deepcopy(target_manifold_dimensionality)

        if verbose: print('\tUser-defined bootstrapping will be performed for a ' + str(n_components) + '-dimensional manifold.')

        bootstrap_pca = reduction.PCA(X[:,bootstrap_variables], scaling=scaling, n_components=n_components)
        PCs = bootstrap_pca.transform(X[:,bootstrap_variables])
        PC_sources = bootstrap_pca.transform(X_source[:,bootstrap_variables], nocenter=True)

        if d_hat_variables is not None:
            depvars = np.hstack((PC_sources, X[:,d_hat_variables]))
            depvar_names = ['SZ' + str(i) for i in range(0,n_components)] + list(variable_names[d_hat_variables])
        else:
            depvars = cp.deepcopy(PC_sources)
            depvar_names = ['SZ' + str(i) for i in range(0,n_components)]

        bootstrap_variance_data = compute_normalized_variance(PCs, depvars, depvar_names=depvar_names, bandwidth_values=bandwidth_values)

        bootstrap_area = cost_function_normalized_variance_derivative(bootstrap_variance_data, weight_area=weight_area, direct_integration=direct_integration)
        if verbose: print('\tCost area:\t%.4f' % bootstrap_area)
        bootstrap_cost_function.append(bootstrap_area)

        if verbose: print('\nVariable(s) ' + ', '.join(list(variable_names[bootstrap_variables])) + ' will be used as bootstrap.')

        bootstrap_toc = time.perf_counter()
        if verbose: print(f'\nBoostrapping time: {(bootstrap_toc - bootstrap_tic)/60:0.1f} minutes.' + '\n' + '-'*50)

    # Iterate the algorithm starting from the bootstrap selection: -------------

    if verbose: print('Optimizing...\n')

    total_tic = time.perf_counter()

    selected_variables = [i for i in bootstrap_variables]

    remaining_variables_list = [i for i in range(0,n_variables) if i not in bootstrap_variables]
    previous_area = np.min(bootstrap_cost_function)

    loop_counter = 0

    while len(remaining_variables_list) > 0:

        loop_counter += 1

        if verbose:
            print('Iteration No.' + str(loop_counter))
            print('Currently adding variables from the following list: ')
            print(variable_names[remaining_variables_list])

        current_cost_function = []

        for i_variable in remaining_variables_list:

            if len(selected_variables) < target_manifold_dimensionality:
                n_components = len(selected_variables) + 1
            else:
                n_components = cp.deepcopy(target_manifold_dimensionality)

            if verbose: print('\tCurrently added variable: ' + variable_names[i_variable])

            current_variables_list = selected_variables + [i_variable]

            pca = reduction.PCA(X[:,current_variables_list], scaling=scaling, n_components=n_components)
            PCs = pca.transform(X[:,current_variables_list])
            PC_sources = pca.transform(X_source[:,current_variables_list], nocenter=True)

            if d_hat_variables is not None:
                depvars = np.hstack((PC_sources, X[:,d_hat_variables]))
                depvar_names = ['SZ' + str(i) for i in range(0,n_components)] + list(variable_names[d_hat_variables])
            else:
                depvars = cp.deepcopy(PC_sources)
                depvar_names = ['SZ' + str(i) for i in range(0,n_components)]

            current_variance_data = compute_normalized_variance(PCs, depvars, depvar_names=depvar_names, bandwidth_values=bandwidth_values)
            current_derivative, current_sigma, _ = normalized_variance_derivative(current_variance_data)

            current_area = cost_function_normalized_variance_derivative(current_variance_data, weight_area=weight_area, direct_integration=direct_integration)
            if verbose: print('\tCost:\t%.4f' % current_area)
            current_cost_function.append(current_area)

            if current_area <= previous_area:
                if verbose: print(colored('\tSAME OR BETTER', 'green'))
            else:
                if verbose: print(colored('\tWORSE', 'red'))

        min_area = np.min(current_cost_function)
        (best_variable_index, ) = np.where(np.array(current_cost_function)==min_area)
        best_variable_index = int(best_variable_index)

        if min_area <= previous_area:
            if verbose: print('\n\tVariable ' + variable_names[remaining_variables_list[best_variable_index]] + ' is added.\n')
            selected_variables.append(remaining_variables_list[best_variable_index])
            remaining_variables_list = [i for i in range(0,n_variables) if i not in selected_variables]
            previous_area = min_area
        else:
            if verbose: print('No variable improves D-hat anymore!')
            break

    if verbose:
        print('\n' + '-'*50)
        print('Final subset:')
        print(', '.join(variable_names[selected_variables]))
        print(selected_variables)
        print('Optimized cumulative area under the D-hat curve: %.4f' % previous_area)
        print('-'*50 + '\n')

    total_toc = time.perf_counter()
    if verbose: print(f'\nOptimization time: {(total_toc - total_tic)/60:0.1f} minutes.' + '\n' + '-'*50)

    return selected_variables

################################################################################
#
# Regression assessment
#
################################################################################

class RegressionAssessment:
    """
    Wrapper class for storing all regression assessment metrics for a given
    regression solution given by the observed dependent variables, :math:`\\pmb{\\phi}_o`,
    and the predicted dependent variables, :math:`\\pmb{\\phi}_p`.

    **Example:**

    .. code:: python

        from PCAfold import PCA, RegressionAssessment
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,3)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Instantiate RegressionAssessment class object:
        regression_metrics = RegressionAssessment(X, X_rec)

        # Access mean absolute error values:
        MAE = regression_metrics.mean_absolute_error

    :param observed:
        ``numpy.ndarray`` specifying the observed values of dependent variables, :math:`\\pmb{\\phi}_o`. It should be of size ``(n_observations,)`` or ``(n_observations,n_variables)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of dependent variables, :math:`\\pmb{\\phi}_p`. It should be of size ``(n_observations,)`` or ``(n_observations,n_variables)``.
    :param variable_names: (optional)
        ``list`` of ``str`` specifying variable names.
    :param norm:
        ``str`` specifying the normalization, :math:`d_{norm}`, for NRMSE computation. It can be one of the following: ``std``, ``range``, ``root_square_mean``, ``root_square_range``, ``root_square_std``, ``abs_mean``.
    :param tolerance:
        ``float`` specifying the tolerance for GDE computation.

    **Attributes:**

    - **coefficient_of_determination** - (read only) ``numpy.ndarray`` specifying the coefficient of determination, :math:`R^2`, values. It has size ``(1,n_variables)``.
    - **mean_absolute_error** - (read only) ``numpy.ndarray`` specifying the mean absolute error (MAE) values. It has size ``(1,n_variables)``.
    - **mean_squared_error** - (read only) ``numpy.ndarray`` specifying the mean squared error (MSE) values. It has size ``(1,n_variables)``.
    - **root_mean_squared_error** - (read only) ``numpy.ndarray`` specifying the root mean squared error (RMSE) values. It has size ``(1,n_variables)``.
    - **normalized root_mean_squared_error** - (read only) ``numpy.ndarray`` specifying the normalized root mean squared error (NRMSE) values. It has size ``(1,n_variables)``.
    - **good_direction_estimate** - (read only) ``float`` specifying the good direction estimate (GDE) value, treating the entire :math:`\\pmb{\\phi}_o` and :math:`\\pmb{\\phi}_p` as vectors.
    """

    def __init__(self, observed, predicted, variable_names=None, norm='std', tolerance=0.05):

        if not isinstance(observed, np.ndarray):
            raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

        try:
            (n_observed,) = np.shape(observed)
            n_var_observed = 1
            observed = observed[:,None]
        except:
            (n_observed, n_var_observed) = np.shape(observed)

        if not isinstance(predicted, np.ndarray):
            raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

        try:
            (n_predicted,) = np.shape(predicted)
            n_var_predicted = 1
            predicted = predicted[:,None]
        except:
            (n_predicted, n_var_predicted) = np.shape(predicted)

        if n_observed != n_predicted:
            raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

        if n_var_observed != n_var_predicted:
            raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

        self.__n_variables = n_var_observed

        if variable_names is not None:
            if not isinstance(variable_names, list):
                raise ValueError("Parameter `variable_names` has to be of type `list`.")
            else:
                if self.__n_variables != len(variable_names):
                    raise ValueError("Parameter `variable_names` has different number of variables than `observed` and `predicted`.")
        else:
            variable_names = []
            for i in range(0,self.__n_variables):
                variable_names.append('X' + str(i+1))

        self.__variable_names = variable_names

        self.__coefficient_of_determination_matrix = np.ones((1,self.__n_variables))
        self.__mean_absolute_error_matrix = np.ones((1,self.__n_variables))
        self.__mean_squared_error_matrix = np.ones((1,self.__n_variables))
        self.__root_mean_squared_error_matrix = np.ones((1,self.__n_variables))
        self.__normalized_root_mean_squared_error_matrix = np.ones((1,self.__n_variables))
        _, self.__good_direction_estimate_value = good_direction_estimate(observed, predicted, tolerance=tolerance)
        self.__good_direction_estimate_matrix = self.__good_direction_estimate_value * np.ones((1,self.__n_variables))

        for i in range(0,self.__n_variables):

            self.__coefficient_of_determination_matrix[0,i] = coefficient_of_determination(observed[:,i], predicted[:,i])
            self.__mean_absolute_error_matrix[0,i] = mean_absolute_error(observed[:,i], predicted[:,i])
            self.__mean_squared_error_matrix[0,i] = mean_squared_error(observed[:,i], predicted[:,i])
            self.__root_mean_squared_error_matrix[0,i] = root_mean_squared_error(observed[:,i], predicted[:,i])
            self.__normalized_root_mean_squared_error_matrix[0,i] = normalized_root_mean_squared_error(observed[:,i], predicted[:,i], norm=norm)

    @property
    def coefficient_of_determination(self):
        return self.__coefficient_of_determination_matrix

    @property
    def mean_absolute_error(self):
        return self.__mean_absolute_error_matrix

    @property
    def mean_squared_error(self):
        return self.__mean_squared_error_matrix

    @property
    def root_mean_squared_error(self):
        return self.__root_mean_squared_error_matrix

    @property
    def normalized_root_mean_squared_error(self):
        return self.__normalized_root_mean_squared_error_matrix

    @property
    def good_direction_estimate(self):
        return self.__good_direction_estimate_value

# ------------------------------------------------------------------------------

    def print_metrics(self, table_format=['raw'], float_format='%.4f'):
        """
        Prints all regression assessment metrics as raw text, in ``tex`` format and/or as ``pandas.DataFrame``.

        **Example:**

        .. code:: python

            from PCAfold import PCA, RegressionAssessment
            import numpy as np

            # Generate dummy data set:
            X = np.random.rand(100,3)

            # Instantiate PCA class object:
            pca_X = PCA(X, scaling='auto', n_components=2)

            # Approximate the data set:
            X_rec = pca_X.reconstruct(pca_X.transform(X))

            # Instantiate RegressionAssessment class object:
            regression_metrics = RegressionAssessment(X, X_rec)

            # Print regression metrics:
            regression_metrics.print_metrics(table_format=['raw', 'tex', 'pandas'], float_format='%.4f')

        .. note::

            Adding ``'raw'`` to the ``table_format`` list will result in printing:

            .. code-block:: text

                --------------------
                X1
                R2: 	0.7889
                MAE:	0.1030
                MSE:	0.0170
                RMSE:	0.1305
                NRMSE:	0.4594
                GDE:	75.0000
                --------------------
                X2
                R2: 	0.5134
                MAE:	0.1640
                MSE:	0.0432
                RMSE:	0.2077
                NRMSE:	0.6976
                GDE:	75.0000
                --------------------
                X3
                R2: 	0.8010
                MAE:	0.0906
                MSE:	0.0132
                RMSE:	0.1148
                NRMSE:	0.4461
                GDE:	75.0000

            Adding ``'tex'`` to the ``table_format`` list will result in printing:

            .. code-block:: text

                \\begin{table}[h!]
                \\begin{center}
                \\begin{tabular}{llll} \\toprule
                 & \\textit{X1} & \\textit{X2} & \\textit{X3} \\\\ \\midrule
                $R^2$ & 0.7889 & 0.5134 & 0.8010 \\\\
                MAE & 0.1030 & 0.1640 & 0.0906 \\\\
                MSE & 0.0170 & 0.0432 & 0.0132 \\\\
                RMSE & 0.1305 & 0.2077 & 0.1148 \\\\
                NRMSE & 0.4594 & 0.6976 & 0.4461 \\\\
                GDE & 75.0000 & 75.0000 & 75.0000 \\\\
                \\end{tabular}
                \\caption{}\\label{}
                \\end{center}
                \\end{table}

            Adding ``'pandas'`` to the ``table_format`` list (works well in Jupyter notebooks) will result in printing:

            .. image:: ../images/generate-pandas-table.png
                :width: 300
                :align: center

        :param table_format: (optional)
            ``list`` of ``str`` specifying the format(s) in which the table should be printed.
            Strings can only be ``'raw'``, ``'tex'`` and/or ``'pandas'``.
        :param float_format: (optional)
            ``str`` specifying the display format for the numerical entries inside the
            table. By default it is set to ``'%.4f'``.
        """

        __table_formats = ['raw', 'tex', 'pandas']

        if not isinstance(table_format, list):
            raise ValueError("Parameter `table_format` has to be of type `str`.")

        for item in table_format:
            if item not in __table_formats:
                raise ValueError("Parameter `table_format` can only contain 'raw', 'tex' and/or 'pandas'.")

        if not isinstance(float_format, str):
            raise ValueError("Parameter `float_format` has to be of type `str`.")

        metrics_names = ['R2', 'MAE', 'MSE', 'RMSE', 'NRMSE', 'GDE']
        metrics_names_tex = ['$R^2$', 'MAE', 'MSE', 'RMSE', 'NRMSE', 'GDE']

        for item in set(table_format):

            if item=='raw':

                for i in range(0,self.__n_variables):

                    print('-'*20 + '\n' + self.__variable_names[i])

                    for j in range(0,len(metrics_names)):

                        metrics = [self.__coefficient_of_determination_matrix[0,i], self.__mean_absolute_error_matrix[0,i], self.__mean_squared_error_matrix[0,i], self.__root_mean_squared_error_matrix[0,i], self.__normalized_root_mean_squared_error_matrix[0,i], self.__good_direction_estimate_matrix[0,i]]
                        print(metrics_names[j] + ':\t' + float_format % metrics[j])

            if item=='tex':

                import pandas as pd

                metrics = np.vstack((self.__coefficient_of_determination_matrix, self.__mean_absolute_error_matrix, self.__mean_squared_error_matrix, self.__root_mean_squared_error_matrix, self.__normalized_root_mean_squared_error_matrix, self.__good_direction_estimate_matrix))
                metrics_table = pd.DataFrame(metrics, columns=self.__variable_names, index=metrics_names_tex)

                generate_tex_table(metrics_table, float_format=float_format)

            if item=='pandas':

                import pandas as pd
                from IPython.display import display
                pandas_format = '{:,' + float_format[1::] + '}'
                pd.options.display.float_format = pandas_format.format

                metrics = np.vstack((self.__coefficient_of_determination_matrix, self.__mean_absolute_error_matrix, self.__mean_squared_error_matrix, self.__root_mean_squared_error_matrix, self.__normalized_root_mean_squared_error_matrix, self.__good_direction_estimate_matrix))
                metrics_table = pd.DataFrame(metrics, columns=self.__variable_names, index=metrics_names_tex)
                display(metrics_table)

# ------------------------------------------------------------------------------

def coefficient_of_determination(observed, predicted):
    """
    Computes the coefficient of determination, :math:`R^2`, value:

    .. math::

        R^2 = 1 - \\frac{\\sum_{i=1}^N (\\phi_{o,i} - \\phi_{p,i})^2}{\\sum_{i=1}^N (\\phi_{o,i} - \\mathrm{mean}(\\phi_{o,i}))^2}

    where :math:`N` is the number of observations, :math:`\\phi_o` is the observed and
    :math:`\\phi_p` is the predicted dependent variable.

    **Example:**

    .. code:: python

        from PCAfold import PCA, coefficient_of_determination
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,3)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Compute the coefficient of determination for the first variable:
        r2 = coefficient_of_determination(X[:,0], X_rec[:,0])

    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable, :math:`\\phi_o`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable, :math:`\\phi_p`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.

    :return:
        - **r2** - coefficient of determination, :math:`R^2`.
    """

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed,) = np.shape(observed)
        n_var_observed = 1
    except:
        (n_observed, n_var_observed) = np.shape(observed)

    if n_var_observed != 1:
        raise ValueError("Parameter `observed` has to be a 0D or 1D vector.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted,) = np.shape(predicted)
        n_var_predicted = 1
    except:
        (n_predicted, n_var_predicted) = np.shape(predicted)

    if n_var_predicted != 1:
        raise ValueError("Parameter `predicted` has to be a 0D or 1D vector.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    r2 = 1. - np.sum((observed - predicted) * (observed - predicted)) / np.sum(
        (observed - np.mean(observed)) * (observed - np.mean(observed)))

    return r2

# ------------------------------------------------------------------------------

def stratified_coefficient_of_determination(observed, predicted, n_bins, use_global_mean=True, verbose=False):
    """
    Computes the stratified coefficient of determination,
    :math:`R^2`, values. Stratified :math:`R^2` is computed separately in each
    of the ``n_bins`` of an observed dependent variable, :math:`\\phi_o`.

    :math:`R_j^2` in the :math:`j^{th}` bin can be computed in two ways:

    - If ``use_global_mean=True``, the mean of the entire observed variable is used as a reference:

    .. math::

        R_j^2 = 1 - \\frac{\\sum_{i=1}^{N_j} (\\phi_{o,i}^{j} - \\phi_{p,i}^{j})^2}{\\sum_{i=1}^{N_j} (\\phi_{o,i}^{j} - \\mathrm{mean}(\\phi_o))^2}

    - If ``use_global_mean=False``, the mean of the considered :math:`j^{th}` bin is used as a reference:

    .. math::

        R_j^2 = 1 - \\frac{\\sum_{i=1}^{N_j} (\\phi_{o,i}^{j} - \\phi_{p,i}^{j})^2}{\\sum_{i=1}^{N_j} (\\phi_{o,i}^{j} - \\mathrm{mean}(\\phi_o^{j}))^2}

    where :math:`N_j` is the number of observations in the :math:`j^{th}` bin and
    :math:`\\phi_p` is the predicted dependent variable.

    .. note::

        After running this function you can call
        ``analysis.plot_stratified_coefficient_of_determination(r2_in_bins, bins_borders)`` on the
        function outputs and it will visualize how stratified :math:`R^2` changes across bins.

    .. warning::

        The stratified :math:`R^2` metric can be misleading if there are large
        variations in point density in an observed variable. For instance, below is a data set
        composed of lines of points that have uniform spacing on the :math:`x` axis
        but become more and more sparse in the direction of increasing :math:`\\phi`
        due to an increasing gradient of :math:`\\phi`.
        If bins are narrow enough (``n_bins`` is high enough), a single bin
        (like the bin bounded by the red dashed lines) can contain only one of
        those lines of points for high value of :math:`\\phi`. :math:`R^2` will then be computed
        for constant, or almost constant observations, even though globally those
        observations lie in a location of a large gradient of the observed variable!

        .. image:: ../images/stratified-r2.png
            :width: 500
            :align: center

    **Example:**

    .. code:: python

        from PCAfold import PCA, stratified_coefficient_of_determination, plot_stratified_coefficient_of_determination
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,10)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Compute stratified R2 in 10 bins of the first variable in a data set:
        (r2_in_bins, bins_borders) = stratified_coefficient_of_determination(X[:,0], X_rec[:,0], n_bins=10, use_global_mean=True, verbose=True)

        # Plot the stratified R2 values:
        plot_stratified_coefficient_of_determination(r2_in_bins, bins_borders)

    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable, :math:`\\phi_o`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable, :math:`\\phi_p`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param n_bins:
        ``int`` specifying the number of bins to consider in a dependent variable (uses the ``preprocess.variable_bins`` function to generate bins).
    :param use_global_mean: (optional)
        ``bool`` specifying if global mean of the observed variable should be used as a reference in :math:`R^2` calculation.
    :param verbose: (optional)
        ``bool`` for printing sizes (number of observations) and :math:`R^2` values in each bin.

    :return:
        - **r2_in_bins** - ``list`` specifying the coefficients of determination :math:`R^2` in each bin. It has length ``n_bins``.
        - **bins_borders** - ``list`` specifying the bins borders that were created to stratify the dependent variable. It has length ``n_bins+1``.
    """

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed,) = np.shape(observed)
        n_var_observed = 1
    except:
        (n_observed, n_var_observed) = np.shape(observed)

    if n_var_observed != 1:
        raise ValueError("Parameter `observed` has to be a 0D or 1D vector.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted,) = np.shape(predicted)
        n_var_predicted = 1
    except:
        (n_predicted, n_var_predicted) = np.shape(predicted)

    if n_var_predicted != 1:
        raise ValueError("Parameter `predicted` has to be a 0D or 1D vector.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    if not isinstance(n_bins, int):
        raise ValueError("Parameter `n_bins` has to be an integer.")

    if n_bins < 1:
        raise ValueError("Parameter `n_bins` has to be an integer larger than 0.")

    if not isinstance(use_global_mean, bool):
        raise ValueError("Parameter `use_global_mean` has to be a boolean.")

    if not isinstance(verbose, bool):
        raise ValueError("Parameter `verbose` has to be a boolean.")

    __observed = observed.ravel()
    __predicted = predicted.ravel()

    (idx, bins_borders) = preprocess.variable_bins(__observed, n_bins, verbose=False)

    r2_in_bins = []

    if use_global_mean:
        global_mean = np.mean(__observed)

    for cl in np.unique(idx):

        (idx_bin,) = np.where(idx==cl)

        if use_global_mean:
            r2 = 1. - np.sum((__observed[idx_bin] - __predicted[idx_bin]) * (__observed[idx_bin] - __predicted[idx_bin])) / np.sum(
                (__observed[idx_bin] - global_mean) * (__observed[idx_bin] - global_mean))
        else:
            r2 = coefficient_of_determination(__observed[idx_bin], __predicted[idx_bin])

        constant_bin_metric_min = np.min(__observed[idx_bin])/np.mean(__observed[idx_bin])
        constant_bin_metric_max = np.max(__observed[idx_bin])/np.mean(__observed[idx_bin])

        if verbose:
            if (abs(constant_bin_metric_min - 1) < 0.01) and (abs(constant_bin_metric_max - 1) < 0.01):
                print('Bin\t' + str(cl+1) + '\t| size\t ' + str(len(idx_bin)) + '\t| R2\t' + str(round(r2,6)) + '\t| ' + colored('This bin has almost constant values.', 'red'))
            else:
                print('Bin\t' + str(cl+1) + '\t| size\t ' + str(len(idx_bin)) + '\t| R2\t' + str(round(r2,6)))

        r2_in_bins.append(r2)

    return (r2_in_bins, bins_borders)

# ------------------------------------------------------------------------------

def mean_absolute_error(observed, predicted):
    """
    Computes the mean absolute error (MAE):

    .. math::

        \\mathrm{MAE} = \\frac{1}{N} \\sum_{i=1}^N | \\phi_{o,i} - \\phi_{p,i} |

    where :math:`N` is the number of observations, :math:`\\phi_o` is the observed and
    :math:`\\phi_p` is the predicted dependent variable.

    **Example:**

    .. code:: python

        from PCAfold import PCA, mean_absolute_error
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,3)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Compute the mean absolute error for the first variable:
        mae = mean_absolute_error(X[:,0], X_rec[:,0])

    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable, :math:`\\phi_o`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable, :math:`\\phi_p`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.

    :return:
        - **mae** - mean absolute error (MAE).
    """

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed,) = np.shape(observed)
        n_var_observed = 1
    except:
        (n_observed, n_var_observed) = np.shape(observed)

    if n_var_observed != 1:
        raise ValueError("Parameter `observed` has to be a 0D or 1D vector.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted,) = np.shape(predicted)
        n_var_predicted = 1
    except:
        (n_predicted, n_var_predicted) = np.shape(predicted)

    if n_var_predicted != 1:
        raise ValueError("Parameter `predicted` has to be a 0D or 1D vector.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    mae = np.sum(abs(observed - predicted)) / n_observed

    return mae

# ------------------------------------------------------------------------------

def mean_squared_error(observed, predicted):
    """
    Computes the mean squared error (MSE):

    .. math::

        \\mathrm{MSE} = \\frac{1}{N} \\sum_{i=1}^N (\\phi_{o,i} - \\phi_{p,i}) ^2

    where :math:`N` is the number of observations, :math:`\\phi_o` is the observed and
    :math:`\\phi_p` is the predicted dependent variable.

    **Example:**

    .. code:: python

        from PCAfold import PCA, mean_squared_error
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,3)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Compute the mean squared error for the first variable:
        mse = mean_squared_error(X[:,0], X_rec[:,0])

    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable, :math:`\\phi_o`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable, :math:`\\phi_p`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.

    :return:
        - **mse** - mean squared error (MSE).
    """

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed,) = np.shape(observed)
        n_var_observed = 1
    except:
        (n_observed, n_var_observed) = np.shape(observed)

    if n_var_observed != 1:
        raise ValueError("Parameter `observed` has to be a 0D or 1D vector.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted,) = np.shape(predicted)
        n_var_predicted = 1
    except:
        (n_predicted, n_var_predicted) = np.shape(predicted)

    if n_var_predicted != 1:
        raise ValueError("Parameter `predicted` has to be a 0D or 1D vector.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    mse = 1.0 / n_observed * np.sum((observed - predicted) * (observed - predicted))

    return mse

# ------------------------------------------------------------------------------

def root_mean_squared_error(observed, predicted):
    """
    Computes the root mean squared error (RMSE):

    .. math::

        \\mathrm{RMSE} = \\sqrt{\\frac{1}{N} \\sum_{i=1}^N (\\phi_{o,i} - \\phi_{p,i}) ^2}

    where :math:`N` is the number of observations, :math:`\\phi_o` is the observed and
    :math:`\\phi_p` is the predicted dependent variable.

    **Example:**

    .. code:: python

        from PCAfold import PCA, root_mean_squared_error
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,3)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Compute the root mean squared error for the first variable:
        rmse = root_mean_squared_error(X[:,0], X_rec[:,0])

    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable, :math:`\\phi_o`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable, :math:`\\phi_p`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.

    :return:
        - **rmse** - root mean squared error (RMSE).
    """

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed,) = np.shape(observed)
        n_var_observed = 1
    except:
        (n_observed, n_var_observed) = np.shape(observed)

    if n_var_observed != 1:
        raise ValueError("Parameter `observed` has to be a 0D or 1D vector.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted,) = np.shape(predicted)
        n_var_predicted = 1
    except:
        (n_predicted, n_var_predicted) = np.shape(predicted)

    if n_var_predicted != 1:
        raise ValueError("Parameter `predicted` has to be a 0D or 1D vector.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    rmse = (mean_squared_error(observed, predicted))**0.5

    return rmse

# ------------------------------------------------------------------------------

def normalized_root_mean_squared_error(observed, predicted, norm='std'):
    """
    Computes the normalized root mean squared error (NRMSE):

    .. math::

        \\mathrm{NRMSE} = \\frac{1}{d_{norm}} \\sqrt{\\frac{1}{N} \\sum_{i=1}^N (\\phi_{o,i} - \\phi_{p,i}) ^2}

    where :math:`d_{norm}` is the normalization factor, :math:`N` is the number of observations, :math:`\\phi_o` is the observed and
    :math:`\\phi_p` is the predicted dependent variable.

    Various normalizations are available:

    +----------------------------+--------------------------+------------------------------------------------------------------------------+
    | Normalization              | ``norm``                 | Normalization factor :math:`d_{norm}`                                        |
    +============================+==========================+==============================================================================+
    | Root square mean           | ``'root_square_mean'``   | :math:`d_{norm} = \sqrt{\mathrm{mean}(\phi_o^2)}`                            |
    +----------------------------+--------------------------+------------------------------------------------------------------------------+
    | Std                        | ``'std'``                | :math:`d_{norm} = \mathrm{std}(\phi_o)`                                      |
    +----------------------------+--------------------------+------------------------------------------------------------------------------+
    | Range                      | ``'range'``              | :math:`d_{norm} = \mathrm{max}(\phi_o) - \mathrm{min}(\phi_o)`               |
    +----------------------------+--------------------------+------------------------------------------------------------------------------+
    | Root square range          | ``'root_square_range'``  | :math:`d_{norm} = \sqrt{\mathrm{max}(\phi_o^2) - \mathrm{min}(\phi_o^2)}``   |
    +----------------------------+--------------------------+------------------------------------------------------------------------------+
    | Root square std            | ``'root_square_std'``    | :math:`d_{norm} = \sqrt{\mathrm{std}(\phi_o^2)}`                             |
    +----------------------------+--------------------------+------------------------------------------------------------------------------+
    | Absolute mean              | ``'abs_mean'``           | :math:`d_{norm} = | \mathrm{mean}(\phi_o) |`                                 |
    +----------------------------+--------------------------+------------------------------------------------------------------------------+

    **Example:**

    .. code:: python

        from PCAfold import PCA, normalized_root_mean_squared_error
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,3)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Compute the root mean squared error for the first variable:
        nrmse = normalized_root_mean_squared_error(X[:,0], X_rec[:,0], norm='std')

    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable, :math:`\\phi_o`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable, :math:`\\phi_p`. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param norm:
        ``str`` specifying the normalization, :math:`d_{norm}`. It can be one of the following: ``std``, ``range``, ``root_square_mean``, ``root_square_range``, ``root_square_std``, ``abs_mean``.

    :return:
        - **nrmse** - normalized root mean squared error (NRMSE).
    """

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed,) = np.shape(observed)
        n_var_observed = 1
    except:
        (n_observed, n_var_observed) = np.shape(observed)

    if n_var_observed != 1:
        raise ValueError("Parameter `observed` has to be a 0D or 1D vector.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted,) = np.shape(predicted)
        n_var_predicted = 1
    except:
        (n_predicted, n_var_predicted) = np.shape(predicted)

    if n_var_predicted != 1:
        raise ValueError("Parameter `predicted` has to be a 0D or 1D vector.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    rmse = root_mean_squared_error(observed, predicted)

    if norm == 'root_square_mean':
        nrmse = rmse/sqrt(np.mean(observed**2))
    elif norm == 'std':
        nrmse = rmse/(np.std(observed))
    elif norm == 'range':
        nrmse = rmse/(np.max(observed) - np.min(observed))
    elif norm == 'root_square_range':
        nrmse = rmse/sqrt(np.max(observed**2) - np.min(observed**2))
    elif norm == 'root_square_std':
        nrmse = rmse/sqrt(np.std(observed**2))
    elif norm == 'abs_mean':
        nrmse = rmse/abs(np.mean(observed))

    return nrmse

# ------------------------------------------------------------------------------

def turning_points(observed, predicted):
    """
    Computes the turning points percentage - the percentage of predicted outputs
    that have the opposite growth tendency to the corresponding observed growth tendency.

    .. warning::

        This function is under construction.

    :return:
        - **turning_points** - turning points percentage in %.
    """

    return turning_points

# ------------------------------------------------------------------------------

def good_estimate(observed, predicted, tolerance=0.05):
    """
    Computes the good estimate (GE) - the percentage of predicted values that
    are within the specified tolerance from the corresponding observed values.

    .. warning::

        This function is under construction.

    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable. It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :parm tolerance:
        ``float`` specifying the tolerance.

    :return:
        - **good_estimate** - good estimate (GE) in %.
    """

    return good_estimate

# ------------------------------------------------------------------------------

def good_direction_estimate(observed, predicted, tolerance=0.05):
    """
    Computes the good direction (GD) and the good direction estimate (GDE).

    GD for observation :math:`i`, is computed as:

    .. math::

        GD_i = \\frac{\\vec{\\phi}_{o,i}}{|| \\vec{\\phi}_{o,i} ||} \\cdot \\frac{\\vec{\\phi}_{p,i}}{|| \\vec{\\phi}_{p,i} ||}

    where :math:`\\vec{\\phi}_o` is the observed vector quantity and :math:`\\vec{\\phi}_p` is the
    predicted vector quantity.

    GDE is computed as the percentage of predicted vector observations whose
    direction is within the specified tolerance from the direction of the
    corresponding observed vector.

    **Example:**

    .. code:: python

        from PCAfold import PCA, good_direction_estimate
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,3)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Compute the vector of good direction and good direction estimate:
        (good_direction, good_direction_estimate) = good_direction_estimate(X, X_rec, tolerance=0.01)

    :param observed:
        ``numpy.ndarray`` specifying the observed vector quantity, :math:`\\vec{\\phi}_o`. It should be of size ``(n_observations,n_dimensions)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted vector quantity, :math:`\\vec{\\phi}_p`. It should be of size ``(n_observations,n_dimensions)``.
    :param tolerance:
        ``float`` specifying the tolerance.

    :return:
        - **good_direction** - ``numpy.ndarray`` specifying the vector of good direction (GD). It has size ``(n_observations,)``.
        - **good_direction_estimate** - good direction estimate (GDE) in %.
    """

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed, n_dimensions_1) = np.shape(observed)
    except:
        raise ValueError("Parameter `observed` should be a matrix.")

    if n_dimensions_1 < 2:
        raise ValueError("Parameter `observed` has to have at least two dimensions.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted, n_dimensions_2) = np.shape(predicted)
    except:
        raise ValueError("Parameter `predicted` should be a matrix.")

    if n_dimensions_2 < 2:
        raise ValueError("Parameter `predicted` has to have at least two dimensions.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    if n_dimensions_1 != n_dimensions_2:
        raise ValueError("Parameter `observed` has different number of dimensions than `predicted`.")

    if not isinstance(tolerance, float):
        raise ValueError("Parameter `tolerance` has to be of type `float`.")

    good_direction = np.zeros((n_observed,))

    for i in range(0,n_observed):
        good_direction[i] = np.dot(observed[i,:]/np.linalg.norm(observed[i,:]), predicted[i,:]/np.linalg.norm(predicted[i,:]))

    (idx_good_direction, ) = np.where(good_direction >= 1.0 - tolerance)

    good_direction_estimate = len(idx_good_direction)/n_observed * 100.0

    return (good_direction, good_direction_estimate)

# ------------------------------------------------------------------------------

def generate_tex_table(data_frame_table, float_format='%.2f', caption='', label=''):
    """
    Generates ``tex`` code for a table stored in a ``pandas.DataFrame``. This function
    can be useful e.g. for printing regression results.

    **Example:**

    .. code:: python

        from PCAfold import PCA, generate_tex_table
        import numpy as np
        import pandas as pd

        # Generate dummy data set:
        X = np.random.rand(100,5)

        # Generate dummy variables names:
        variable_names = ['A1', 'A2', 'A3', 'A4', 'A5']

        # Instantiate PCA class object:
        pca_q2 = PCA(X, scaling='auto', n_components=2, use_eigendec=True, nocenter=False)
        pca_q3 = PCA(X, scaling='auto', n_components=3, use_eigendec=True, nocenter=False)

        # Calculate the R2 values:
        r2_q2 = pca_q2.calculate_r2(X)[None,:]
        r2_q3 = pca_q3.calculate_r2(X)[None,:]

        # Generate pandas.DataFrame from the R2 values:
        r2_table = pd.DataFrame(np.vstack((r2_q2, r2_q3)), columns=variable_names, index=['PCA, $q=2$', 'PCA, $q=3$'])

        # Generate tex code for the table:
        generate_tex_table(r2_table, float_format="%.3f", caption='$R^2$ values.', label='r2-values')

    .. note::

        The code above will produce ``tex`` code:

        .. code-block:: text

            \\begin{table}[h!]
            \\begin{center}
            \\begin{tabular}{llllll} \\toprule
             & \\textit{A1} & \\textit{A2} & \\textit{A3} & \\textit{A4} & \\textit{A5} \\\\ \\midrule
            PCA, $q=2$ & 0.507 & 0.461 & 0.485 & 0.437 & 0.611 \\\\
            PCA, $q=3$ & 0.618 & 0.658 & 0.916 & 0.439 & 0.778 \\\\
            \\end{tabular}
            \\caption{$R^2$ values.}\\label{r2-values}
            \\end{center}
            \\end{table}

        Which, when compiled, will result in a table:

        .. image:: ../images/generate-tex-table.png
            :width: 450
            :align: center

    :param data_frame_table:
        ``pandas.DataFrame`` specifying the table to convert to ``tex`` code. It can include column names and
        index names.
    :param float_format:
        ``str`` specifying the display format for the numerical entries inside the
        table. By default it is set to ``'%.2f'``.
    :param caption:
        ``str`` specifying caption for the table.
    :param label:
        ``str`` specifying label for the table.
    """

    (n_rows, n_columns) = np.shape(data_frame_table)
    rows_labels = data_frame_table.index.values
    columns_labels = data_frame_table.columns.values

    print('')
    print(r'\begin{table}[h!]')
    print(r'\begin{center}')
    print(r'\begin{tabular}{' + ''.join(['l' for i in range(0, n_columns+1)]) + r'} \toprule')
    print(' & ' + ' & '.join([r'\textit{' + name + '}' for name in columns_labels]) + r' \\ \midrule')

    for row_i, row_label in enumerate(rows_labels):

        row_values = list(data_frame_table.iloc[row_i,:])
        print(row_label + r' & '+  ' & '.join([str(float_format % value) for value in row_values]) + r' \\')

    print(r'\end{tabular}')
    print(r'\caption{' + caption + r'}\label{' + label + '}')
    print(r'\end{center}')
    print(r'\end{table}')
    print('')

################################################################################
#
# Plotting functions
#
################################################################################

def plot_2d_regression(x, observed, predicted, x_label=None, y_label=None, figure_size=(7,7), title=None, save_filename=None):
    """
    Plots the result of regression of a dependent variable on top
    of a one-dimensional manifold defined by a single independent variable ``x``.

    **Example:**

    .. code:: python

        from PCAfold import PCA, plot_2d_regression
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,10)

        # Obtain two-dimensional manifold from PCA:
        pca_X = PCA(X)
        PCs = pca_X.transform(X)
        X_rec = pca_X.reconstruct(PCs)

        # Plot the manifold:
        plt = plot_2d_regression(X[:,0], X[:,0], X_rec[:,0], x_label='$x$', y_label='$y$', figure_size=(10,10), title='2D regression', save_filename='2d-regression.pdf')
        plt.close()

    :param x:
        ``numpy.ndarray`` specifying the variable on the :math:`x`-axis. It should be of size ``(n_observations,)`` or ``(n_observations,1)``.
    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable.
        It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable.
        It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param x_label: (optional)
        ``str`` specifying :math:`x`-axis label annotation. If set to ``None``
        label will not be plotted.
    :param y_label: (optional)
        ``str`` specifying :math:`y`-axis label annotation. If set to ``None``
        label will not be plotted.
    :param figure_size: (optional)
        ``tuple`` specifying figure size.
    :param title: (optional)
        ``str`` specifying plot title. If set to ``None`` title will not be
        plotted.
    :param save_filename: (optional)
        ``str`` specifying plot save location/filename. If set to ``None``
        plot will not be saved. You can also set a desired file extension,
        for instance ``.pdf``. If the file extension is not specified, the default
        is ``.png``.

    :return:
        - **plt** - ``matplotlib.pyplot`` plot handle.
    """

    if not isinstance(x, np.ndarray):
        raise ValueError("Parameter `x` has to be of type `numpy.ndarray`.")

    try:
        (n_x,) = np.shape(x)
        n_var_x = 1
    except:
        (n_x, n_var_x) = np.shape(x)

    if n_var_x != 1:
        raise ValueError("Parameter `x` has to be a 0D or 1D vector.")

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed,) = np.shape(observed)
        n_var_observed = 1
    except:
        (n_observed, n_var_observed) = np.shape(observed)

    if n_var_observed != 1:
        raise ValueError("Parameter `observed` has to be a 0D or 1D vector.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted,) = np.shape(predicted)
        n_var_predicted = 1
    except:
        (n_predicted, n_var_predicted) = np.shape(predicted)

    if n_var_predicted != 1:
        raise ValueError("Parameter `predicted` has to be a 0D or 1D vector.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    if n_x != n_observed:
        raise ValueError("Parameter `observed` has different number of elements than `x`.")

    if n_x != n_predicted:
        raise ValueError("Parameter `predicted` has different number of elements than `x`.")

    if x_label is not None:
        if not isinstance(x_label, str):
            raise ValueError("Parameter `x_label` has to be of type `str`.")

    if y_label is not None:
        if not isinstance(y_label, str):
            raise ValueError("Parameter `y_label` has to be of type `str`.")

    if not isinstance(figure_size, tuple):
        raise ValueError("Parameter `figure_size` has to be of type `tuple`.")

    if title is not None:
        if not isinstance(title, str):
            raise ValueError("Parameter `title` has to be of type `str`.")

    if save_filename is not None:
        if not isinstance(save_filename, str):
            raise ValueError("Parameter `save_filename` has to be of type `str`.")

    color_observed = '#191b27'
    color_predicted = '#C7254E'

    fig = plt.figure(figsize=figure_size)

    scat = plt.scatter(x.ravel(), observed.ravel(), c=color_observed, marker='o', s=scatter_point_size, alpha=0.1)
    scat = plt.scatter(x.ravel(), predicted.ravel(), c=color_predicted, marker='o', s=scatter_point_size, alpha=0.4)

    if x_label != None: plt.xlabel(x_label, **csfont, fontsize=font_labels)
    if y_label != None: plt.ylabel(y_label, **csfont, fontsize=font_labels)
    plt.xticks(fontsize=font_axes, **csfont)
    plt.yticks(fontsize=font_axes, **csfont)
    plt.grid(alpha=grid_opacity)
    lgnd = plt.legend(['Observed', 'Predicted'], fontsize=font_legend, loc="best")
    lgnd.legendHandles[0]._sizes = [marker_size*5]
    lgnd.legendHandles[1]._sizes = [marker_size*5]

    if title != None: plt.title(title, **csfont, fontsize=font_title)
    if save_filename != None: plt.savefig(save_filename, dpi=save_dpi, bbox_inches='tight')

    return plt

# ------------------------------------------------------------------------------

def plot_3d_regression(x, y, observed, predicted, elev=45, azim=-45, x_label=None, y_label=None, z_label=None, figure_size=(7,7), title=None, save_filename=None):
    """
    Plots the result of regression of a dependent variable on top
    of a two-dimensional manifold defined by two independent variables ``x`` and ``y``.

    **Example:**

    .. code:: python

        from PCAfold import PCA, plot_3d_regression
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,10)

        # Obtain three-dimensional manifold from PCA:
        pca_X = PCA(X)
        PCs = pca_X.transform(X)
        X_rec = pca_X.reconstruct(PCs)

        # Plot the manifold:
        plt = plot_3d_regression(X[:,0], X[:,1], X[:,0], X_rec[:,0], elev=45, azim=-45, x_label='$x$', y_label='$y$', z_label='$z$', figure_size=(10,10), title='3D regression', save_filename='3d-regression.pdf')
        plt.close()

    :param x:
        ``numpy.ndarray`` specifying the variable on the :math:`x`-axis. It should be of size ``(n_observations,)`` or ``(n_observations,1)``.
    :param y:
        ``numpy.ndarray`` specifying the variable on the :math:`y`-axis. It should be of size ``(n_observations,)`` or ``(n_observations,1)``.
    :param observed:
        ``numpy.ndarray`` specifying the observed values of a single dependent variable.
        It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param predicted:
        ``numpy.ndarray`` specifying the predicted values of a single dependent variable.
        It should be of size ``(n_observations,)`` or ``(n_observations, 1)``.
    :param elev: (optional)
        elevation angle.
    :param azim: (optional)
        azimuth angle.
    :param x_label: (optional)
        ``str`` specifying :math:`x`-axis label annotation. If set to ``None``
        label will not be plotted.
    :param y_label: (optional)
        ``str`` specifying :math:`y`-axis label annotation. If set to ``None``
        label will not be plotted.
    :param z_label: (optional)
        ``str`` specifying :math:`z`-axis label annotation. If set to ``None``
        label will not be plotted.
    :param figure_size: (optional)
        ``tuple`` specifying figure size.
    :param title: (optional)
        ``str`` specifying plot title. If set to ``None`` title will not be
        plotted.
    :param save_filename: (optional)
        ``str`` specifying plot save location/filename. If set to ``None``
        plot will not be saved. You can also set a desired file extension,
        for instance ``.pdf``. If the file extension is not specified, the default
        is ``.png``.

    :return:
        - **plt** - ``matplotlib.pyplot`` plot handle.
    """

    from mpl_toolkits.mplot3d import Axes3D

    if not isinstance(x, np.ndarray):
        raise ValueError("Parameter `x` has to be of type `numpy.ndarray`.")

    try:
        (n_x,) = np.shape(x)
        n_var_x = 1
    except:
        (n_x, n_var_x) = np.shape(x)

    if n_var_x != 1:
        raise ValueError("Parameter `x` has to be a 0D or 1D vector.")

    if not isinstance(y, np.ndarray):
        raise ValueError("Parameter `y` has to be of type `numpy.ndarray`.")

    try:
        (n_y,) = np.shape(y)
        n_var_y = 1
    except:
        (n_y, n_var_y) = np.shape(y)

    if n_var_y != 1:
        raise ValueError("Parameter `y` has to be a 0D or 1D vector.")

    if not isinstance(observed, np.ndarray):
        raise ValueError("Parameter `observed` has to be of type `numpy.ndarray`.")

    try:
        (n_observed,) = np.shape(observed)
        n_var_observed = 1
    except:
        (n_observed, n_var_observed) = np.shape(observed)

    if n_var_observed != 1:
        raise ValueError("Parameter `observed` has to be a 0D or 1D vector.")

    if not isinstance(predicted, np.ndarray):
        raise ValueError("Parameter `predicted` has to be of type `numpy.ndarray`.")

    try:
        (n_predicted,) = np.shape(predicted)
        n_var_predicted = 1
    except:
        (n_predicted, n_var_predicted) = np.shape(predicted)

    if n_var_predicted != 1:
        raise ValueError("Parameter `predicted` has to be a 0D or 1D vector.")

    if n_observed != n_predicted:
        raise ValueError("Parameter `observed` has different number of elements than `predicted`.")

    if n_x != n_observed:
        raise ValueError("Parameter `observed` has different number of elements than `x`, `y` and `z`.")

    if n_x != n_predicted:
        raise ValueError("Parameter `predicted` has different number of elements than `x`, `y` and `z`.")

    if x_label is not None:
        if not isinstance(x_label, str):
            raise ValueError("Parameter `x_label` has to be of type `str`.")

    if y_label is not None:
        if not isinstance(y_label, str):
            raise ValueError("Parameter `y_label` has to be of type `str`.")

    if z_label is not None:
        if not isinstance(z_label, str):
            raise ValueError("Parameter `z_label` has to be of type `str`.")

    if not isinstance(figure_size, tuple):
        raise ValueError("Parameter `figure_size` has to be of type `tuple`.")

    if title is not None:
        if not isinstance(title, str):
            raise ValueError("Parameter `title` has to be of type `str`.")

    if save_filename is not None:
        if not isinstance(save_filename, str):
            raise ValueError("Parameter `save_filename` has to be of type `str`.")

    color_observed = '#191b27'
    color_predicted = '#C7254E'

    fig = plt.figure(figsize=figure_size)
    ax = fig.add_subplot(111, projection='3d')

    scat = ax.scatter(x.ravel(), y.ravel(), observed.ravel(), c=color_observed, marker='o', s=scatter_point_size, alpha=0.1)
    scat = ax.scatter(x.ravel(), y.ravel(), predicted.ravel(), c=color_predicted, marker='o', s=scatter_point_size, alpha=0.4)

    if x_label != None: ax.set_xlabel(x_label, **csfont, fontsize=font_labels, rotation=0, labelpad=20)
    if y_label != None: ax.set_ylabel(y_label, **csfont, fontsize=font_labels, rotation=0, labelpad=20)
    if z_label != None: ax.set_zlabel(z_label, **csfont, fontsize=font_labels, rotation=0, labelpad=20)

    ax.tick_params(pad=5)
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    ax.xaxis.pane.set_edgecolor('w')
    ax.yaxis.pane.set_edgecolor('w')
    ax.zaxis.pane.set_edgecolor('w')
    ax.view_init(elev=elev, azim=azim)
    ax.grid(alpha=grid_opacity)

    for label in (ax.get_xticklabels()):
        label.set_fontsize(font_axes)
    for label in (ax.get_yticklabels()):
        label.set_fontsize(font_axes)
    for label in (ax.get_zticklabels()):
        label.set_fontsize(font_axes)

    lgnd = plt.legend(['Observed', 'Predicted'], fontsize=font_legend, bbox_to_anchor=(0.9,0.9), loc="upper left")
    lgnd.legendHandles[0]._sizes = [marker_size*5]
    lgnd.legendHandles[1]._sizes = [marker_size*5]

    if title != None: ax.set_title(title, **csfont, fontsize=font_title)
    if save_filename != None: plt.savefig(save_filename, dpi=save_dpi, bbox_inches='tight')

    return plt

# ------------------------------------------------------------------------------

def plot_normalized_variance(variance_data, plot_variables=[], color_map='Blues', figure_size=(10,5), title=None, save_filename=None):
    """
    This function plots normalized variance :math:`\mathcal{N}(\sigma)` over
    bandwith values :math:`\sigma` from an object of a ``VarianceData`` class.

    *Note:* this function can accomodate plotting up to 18 variables at once.
    You can specify which variables should be plotted using ``plot_variables`` list.

    **Example:**

    .. code:: python

        from PCAfold import PCA, compute_normalized_variance, plot_normalized_variance
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,5)

        # Perform PCA to obtain the low-dimensional manifold:
        pca_X = PCA(X, n_components=2)
        principal_components = pca_X.transform(X)

        # Compute normalized variance quantities:
        variance_data = compute_normalized_variance(principal_components, X, depvar_names=['A', 'B', 'C', 'D', 'E'], bandwidth_values=np.logspace(-3, 1, 20), scale_unit_box=True)

        # Plot normalized variance quantities:
        plt = plot_normalized_variance(variance_data, plot_variables=[0,1,2], color_map='Blues', figure_size=(10,5), title='Normalized variance', save_filename='N.pdf')
        plt.close()

    :param variance_data:
        an object of ``VarianceData`` class objects whose normalized variance quantities
        should be plotted.
    :param plot_variables: (optional)
        ``list`` of ``int`` specifying indices of variables to be plotted.
        By default, all variables are plotted.
    :param color_map: (optional)
        ``str`` or ``matplotlib.colors.ListedColormap`` specifying the colormap to use as per ``matplotlib.cm``. Default is ``'Blues'``.
    :param figure_size: (optional)
        ``tuple`` specifying figure size.
    :param title: (optional)
        ``str`` specifying plot title. If set to ``None`` title will not be
        plotted.
    :param save_filename: (optional)
        ``str`` specifying plot save location/filename. If set to ``None``
        plot will not be saved. You can also set a desired file extension,
        for instance ``.pdf``. If the file extension is not specified, the default
        is ``.png``.

    :return:
        - **plt** - ``matplotlib.pyplot`` plot handle.
    """

    from matplotlib import cm
    color_map_colors = cm.get_cmap(color_map)

    markers_list = ["o-","v-","^-","<-",">-","s-","p-","P-","*-","h-","H-","+-","x-","X-","D-","d-","|-","_-"]

    # Extract quantities from the VarianceData class object:
    variable_names = variance_data.variable_names
    bandwidth_values = variance_data.bandwidth_values
    normalized_variance = variance_data.normalized_variance

    if len(plot_variables) != 0:
        variables_to_plot = []
        for i in plot_variables:
            variables_to_plot.append(variable_names[i])
    else:
        variables_to_plot = variable_names

    n_variables = len(variables_to_plot)

    if n_variables > 18:
        raise ValueError("Only 18 variables can be plotted at once. Consider pre-selecting the variables to plot using `plot_variables` parameter.")

    if n_variables == 1:
        variable_colors = np.flipud(color_map_colors([0.8]))
    else:
        variable_colors = np.flipud(color_map_colors(np.linspace(0.2, 0.8, n_variables)))

    figure = plt.figure(figsize=figure_size)

    # Plot the normalized variance:
    for i, variable_name in enumerate(variables_to_plot):
        plt.semilogx(bandwidth_values, normalized_variance[variable_name], markers_list[i], label=variable_name, color=variable_colors[i])

    plt.xlabel('$\sigma$', fontsize=font_labels, **csfont)
    plt.ylabel('$N(\sigma)$', fontsize=font_labels, **csfont)
    plt.grid(alpha=grid_opacity)

    if n_variables <=5:
        plt.legend(loc='best', fancybox=True, shadow=True, ncol=1, fontsize=font_legend, markerscale=marker_scale_legend)
    else:
        plt.legend(bbox_to_anchor=(1.05,1), fancybox=True, shadow=True, ncol=2, fontsize=font_legend, markerscale=marker_scale_legend)

    if title != None: plt.title(title, fontsize=font_title, **csfont)
    if save_filename != None: plt.savefig(save_filename, dpi=save_dpi, bbox_inches='tight')

    return plt

# ------------------------------------------------------------------------------

def plot_normalized_variance_comparison(variance_data_tuple, plot_variables_tuple, color_map_tuple, figure_size=(10,5), title=None, save_filename=None):
    """
    This function plots a comparison of normalized variance :math:`\mathcal{N}(\sigma)` over
    bandwith values :math:`\sigma` from several objects of a ``VarianceData`` class.

    *Note:* this function can accomodate plotting up to 18 variables at once.
    You can specify which variables should be plotted using ``plot_variables`` list.

    **Example:**

    .. code:: python

        from PCAfold import PCA, compute_normalized_variance, plot_normalized_variance_comparison
        import numpy as np

        # Generate dummy data sets:
        X = np.random.rand(100,5)
        Y = np.random.rand(100,5)

        # Perform PCA to obtain low-dimensional manifolds:
        pca_X = PCA(X, n_components=2)
        pca_Y = PCA(Y, n_components=2)
        principal_components_X = pca_X.transform(X)
        principal_components_Y = pca_Y.transform(Y)

        # Compute normalized variance quantities:
        variance_data_X = compute_normalized_variance(principal_components_X, X, depvar_names=['A', 'B', 'C', 'D', 'E'], bandwidth_values=np.logspace(-3, 2, 20), scale_unit_box=True)
        variance_data_Y = compute_normalized_variance(principal_components_Y, Y, depvar_names=['F', 'G', 'H', 'I', 'J'], bandwidth_values=np.logspace(-3, 2, 20), scale_unit_box=True)

        # Plot a comparison of normalized variance quantities:
        plt = plot_normalized_variance_comparison((variance_data_X, variance_data_Y), ([0,1,2], [0,1,2]), ('Blues', 'Reds'), title='Normalized variance comparison', save_filename='N.pdf')
        plt.close()

    :param variance_data_tuple:
        ``tuple`` of ``VarianceData`` class objects whose normalized variance quantities
        should be compared on one plot. For instance: ``(variance_data_1, variance_data_2)``.
    :param plot_variables_tuple:
        ``list`` of ``int`` specifying indices of variables to be plotted.
        It should have as many elements as there are ``VarianceData`` class objects supplied.
        For instance: ``([], [])`` will plot all variables.
    :param color_map: (optional)
        ``tuple`` of ``str`` or ``matplotlib.colors.ListedColormap`` specifying the colormap to use as per ``matplotlib.cm``.
        It should have as many elements as there are ``VarianceData`` class objects supplied.
        For instance: ``('Blues', 'Reds')``.
    :param figure_size: (optional)
        ``tuple`` specifying figure size.
    :param title: (optional)
        ``str`` specifying plot title. If set to ``None`` title will not be
        plotted.
    :param save_filename: (optional)
        ``str`` specifying plot save location/filename. If set to ``None``
        plot will not be saved. You can also set a desired file extension,
        for instance ``.pdf``. If the file extension is not specified, the default
        is ``.png``.

    :return:
        - **plt** - ``matplotlib.pyplot`` plot handle.
    """

    from matplotlib import cm

    markers_list = ["o-","v-","^-","<-",">-","s-","p-","P-","*-","h-","H-","+-","x-","X-","D-","d-","|-","_-"]

    figure = plt.figure(figsize=figure_size)

    variable_count = 0

    for variance_data, plot_variables, color_map in zip(variance_data_tuple, plot_variables_tuple, color_map_tuple):

        color_map_colors = cm.get_cmap(color_map)

        # Extract quantities from the VarianceData class object:
        variable_names = variance_data.variable_names
        bandwidth_values = variance_data.bandwidth_values
        normalized_variance = variance_data.normalized_variance

        if len(plot_variables) != 0:
            variables_to_plot = []
            for i in plot_variables:
                variables_to_plot.append(variable_names[i])
        else:
            variables_to_plot = variable_names

        n_variables = len(variables_to_plot)

        if n_variables == 1:
            variable_colors = np.flipud(color_map_colors([0.8]))
        else:
            variable_colors = np.flipud(color_map_colors(np.linspace(0.2, 0.8, n_variables)))

        # Plot the normalized variance:
        for i, variable_name in enumerate(variables_to_plot):
            plt.semilogx(bandwidth_values, normalized_variance[variable_name], markers_list[variable_count], label=variable_name, color=variable_colors[i])

            variable_count = variable_count + 1

    plt.xlabel('$\sigma$', fontsize=font_labels, **csfont)
    plt.ylabel('$N(\sigma)$', fontsize=font_labels, **csfont)
    plt.grid(alpha=grid_opacity)

    if variable_count <=5:
        plt.legend(loc='best', fancybox=True, shadow=True, ncol=1, fontsize=font_legend, markerscale=marker_scale_legend)
    else:
        plt.legend(bbox_to_anchor=(1.05,1), fancybox=True, shadow=True, ncol=2, fontsize=font_legend, markerscale=marker_scale_legend)

    if title != None: plt.title(title, fontsize=font_title, **csfont)
    if save_filename != None: plt.savefig(save_filename, dpi=save_dpi, bbox_inches='tight')

    return plt

# ------------------------------------------------------------------------------

def plot_normalized_variance_derivative(variance_data, plot_variables=[], color_map='Blues', figure_size=(10,5), title=None, save_filename=None):
    """
    This function plots a scaled normalized variance derivative (computed over logarithmically scaled bandwidths), :math:`\hat{\mathcal{D}(\sigma)}`,
    over bandwith values :math:`\sigma` from an object of a ``VarianceData`` class.

    *Note:* this function can accomodate plotting up to 18 variables at once.
    You can specify which variables should be plotted using ``plot_variables`` list.

    Example is similar to that found for ``plot_normalized_variance``.

    :param variance_data:
        an object of ``VarianceData`` class objects whose normalized variance derivative quantities
        should be plotted.
    :param plot_variables: (optional)
        ``list`` of ``int`` specifying indices of variables to be plotted.
        By default, all variables are plotted.
    :param color_map: (optional)
        ``str`` or ``matplotlib.colors.ListedColormap`` specifying the colormap to use as per ``matplotlib.cm``. Default is ``'Blues'``.
    :param figure_size: (optional)
        ``tuple`` specifying figure size.
    :param title: (optional)
        ``str`` specifying plot title. If set to ``None`` title will not be
        plotted.
    :param save_filename: (optional)
        ``str`` specifying plot save location/filename. If set to ``None``
        plot will not be saved. You can also set a desired file extension,
        for instance ``.pdf``. If the file extension is not specified, the default
        is ``.png``.

    :return:
        - **plt** - ``matplotlib.pyplot`` plot handle.
    """

    from matplotlib import cm
    color_map_colors = cm.get_cmap(color_map)

    markers_list = ["o-","v-","^-","<-",">-","s-","p-","P-","*-","h-","H-","+-","x-","X-","D-","d-","|-","_-"]

    # Extract quantities from the VarianceData class object:
    variable_names = variance_data.variable_names
    derivatives, bandwidth_values, _ = normalized_variance_derivative(variance_data)

    if len(plot_variables) != 0:
        variables_to_plot = []
        for i in plot_variables:
            variables_to_plot.append(variable_names[i])
    else:
        variables_to_plot = variable_names

    n_variables = len(variables_to_plot)

    if n_variables > 18:
        raise ValueError("Only 18 variables can be plotted at once. Consider pre-selecting the variables to plot using `plot_variables` parameter.")

    if n_variables == 1:
        variable_colors = np.flipud(color_map_colors([0.8]))
    else:
        variable_colors = np.flipud(color_map_colors(np.linspace(0.2, 0.8, n_variables)))

    figure = plt.figure(figsize=figure_size)

    # Plot the normalized variance derivative:
    for i, variable_name in enumerate(variables_to_plot):
        plt.semilogx(bandwidth_values, derivatives[variable_name], markers_list[i], label=variable_name, color=variable_colors[i])

    plt.xlabel('$\sigma$', fontsize=font_labels, **csfont)
    plt.ylabel('$\hat{\mathcal{D}}(\sigma)$', fontsize=font_labels, **csfont)
    plt.grid(alpha=grid_opacity)

    if n_variables <=5:
        plt.legend(loc='best', fancybox=True, shadow=True, ncol=1, fontsize=font_legend, markerscale=marker_scale_legend)
    else:
        plt.legend(bbox_to_anchor=(1.05,1), fancybox=True, shadow=True, ncol=2, fontsize=font_legend, markerscale=marker_scale_legend)

    if title != None: plt.title(title, fontsize=font_title, **csfont)
    if save_filename != None: plt.savefig(save_filename, dpi=save_dpi, bbox_inches='tight')

    return plt

# ------------------------------------------------------------------------------

def plot_normalized_variance_derivative_comparison(variance_data_tuple, plot_variables_tuple, color_map_tuple, figure_size=(10,5), title=None, save_filename=None):
    """
    This function plots a comparison of scaled normalized variance derivative (computed over logarithmically scaled bandwidths), :math:`\hat{\mathcal{D}(\sigma)}`,
    over bandwith values :math:`\sigma` from an object of a ``VarianceData`` class.

    *Note:* this function can accomodate plotting up to 18 variables at once.
    You can specify which variables should be plotted using ``plot_variables`` list.

    Example is similar to that found for ``plot_normalized_variance_comparison``.

    :param variance_data_tuple:
        ``tuple`` of ``VarianceData`` class objects whose normalized variance derivative quantities
        should be compared on one plot. For instance: ``(variance_data_1, variance_data_2)``.
    :param plot_variables_tuple:
        ``list`` of ``int`` specifying indices of variables to be plotted.
        It should have as many elements as there are ``VarianceData`` class objects supplied.
        For instance: ``([], [])`` will plot all variables.
    :param color_map: (optional)
        ``tuple`` of ``str`` or ``matplotlib.colors.ListedColormap`` specifying the colormap to use as per ``matplotlib.cm``.
        It should have as many elements as there are ``VarianceData`` class objects supplied.
        For instance: ``('Blues', 'Reds')``.
    :param figure_size: (optional)
        ``tuple`` specifying figure size.
    :param title: (optional)
        ``str`` specifying plot title. If set to ``None`` title will not be
        plotted.
    :param save_filename: (optional)
        ``str`` specifying plot save location/filename. If set to ``None``
        plot will not be saved. You can also set a desired file extension,
        for instance ``.pdf``. If the file extension is not specified, the default
        is ``.png``.

    :return:
        - **plt** - ``matplotlib.pyplot`` plot handle.
    """

    from matplotlib import cm

    markers_list = ["o-","v-","^-","<-",">-","s-","p-","P-","*-","h-","H-","+-","x-","X-","D-","d-","|-","_-"]

    figure = plt.figure(figsize=figure_size)

    variable_count = 0

    for variance_data, plot_variables, color_map in zip(variance_data_tuple, plot_variables_tuple, color_map_tuple):

        color_map_colors = cm.get_cmap(color_map)

        # Extract quantities from the VarianceData class object:
        variable_names = variance_data.variable_names
        derivatives, bandwidth_values, _ = normalized_variance_derivative(variance_data)

        if len(plot_variables) != 0:
            variables_to_plot = []
            for i in plot_variables:
                variables_to_plot.append(variable_names[i])
        else:
            variables_to_plot = variable_names

        n_variables = len(variables_to_plot)

        if n_variables == 1:
            variable_colors = np.flipud(color_map_colors([0.8]))
        else:
            variable_colors = np.flipud(color_map_colors(np.linspace(0.2, 0.8, n_variables)))

        # Plot the normalized variance:
        for i, variable_name in enumerate(variables_to_plot):
            plt.semilogx(bandwidth_values, derivatives[variable_name], markers_list[variable_count], label=variable_name, color=variable_colors[i])

            variable_count = variable_count + 1

    plt.xlabel('$\sigma$', fontsize=font_labels, **csfont)
    plt.ylabel('$\hat{\mathcal{D}}(\sigma)$', fontsize=font_labels, **csfont)
    plt.grid(alpha=grid_opacity)

    if variable_count <=5:
        plt.legend(loc='best', fancybox=True, shadow=True, ncol=1, fontsize=font_legend, markerscale=marker_scale_legend)
    else:
        plt.legend(bbox_to_anchor=(1.05,1), fancybox=True, shadow=True, ncol=2, fontsize=font_legend, markerscale=marker_scale_legend)

    if title != None: plt.title(title, fontsize=font_title, **csfont)
    if save_filename != None: plt.savefig(save_filename, dpi=save_dpi, bbox_inches='tight')

    return plt

# ------------------------------------------------------------------------------

def plot_stratified_coefficient_of_determination(r2_in_bins, bins_borders, variable_name=None, figure_size=(10,5), title=None, save_filename=None):
    """
    This function plots the stratified coefficient of determination :math:`R^2`
    across bins of a dependent variable.

    **Example:**

    .. code:: python

        from PCAfold import PCA, stratified_coefficient_of_determination, plot_stratified_coefficient_of_determination
        import numpy as np

        # Generate dummy data set:
        X = np.random.rand(100,10)

        # Instantiate PCA class object:
        pca_X = PCA(X, scaling='auto', n_components=2)

        # Approximate the data set:
        X_rec = pca_X.reconstruct(pca_X.transform(X))

        # Compute stratified R2 in 10 bins of the first variable in a data set:
        (r2_in_bins, bins_borders) = stratified_coefficient_of_determination(X[:,0], X_rec[:,0], n_bins=10, use_global_mean=True, verbose=True)

        # Visualize how R2 changes across bins:
        plt = plot_stratified_coefficient_of_determination(r2_in_bins, bins_borders, variable_name='$X_1$', figure_size=(10,5), title='Stratified R2', save_filename='r2.pdf')
        plt.close()

    :param r2_in_bins:
        list of coefficients of determination :math:`R^2` in each bin as per ``analysis.stratified_coefficient_of_determination`` function.
    :param bins_borders:
        list of bins borders that were created to stratify the dependent variable as per ``analysis.stratified_coefficient_of_determination`` function.
    :param variable_name: (optional)
        string specifying the name of the variable for which :math:`R^2` were computed. If set to ``None``
        label on the x-axis will not be plotted.
    :param figure_size: (optional)
        ``tuple`` specifying figure size.
    :param title: (optional)
        ``str`` specifying plot title. If set to ``None`` title will not be
        plotted.
    :param save_filename: (optional)
        ``str`` specifying plot save location/filename. If set to ``None``
        plot will not be saved. You can also set a desired file extension,
        for instance ``.pdf``. If the file extension is not specified, the default
        is ``.png``.

    :return:
        - **plt** - ``matplotlib.pyplot`` plot handle.
    """

    bin_length = bins_borders[1] - bins_borders[0]
    bin_centers = bins_borders[0:-1] + bin_length/2

    figure = plt.figure(figsize=figure_size)
    plt.scatter(bin_centers, r2_in_bins, c='#191b27')
    plt.grid(alpha=grid_opacity)
    if variable_name != None: plt.xlabel(variable_name, **csfont, fontsize=font_labels)
    plt.ylabel('$R^2$ [-]', **csfont, fontsize=font_labels)

    if title != None: plt.title(title, fontsize=font_title, **csfont)
    if save_filename != None: plt.savefig(save_filename, dpi=save_dpi, bbox_inches='tight')

    return plt
