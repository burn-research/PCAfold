"""This is the base PCAfold directory."""

__author__ = "Kamila Zdybal, Elizabeth Armstrong, Alessandro Parente and James C. Sutherland"
__copyright__ = "Copyright (c) 2020, Kamila Zdybal and Elizabeth Armstrong"
__credits__ = ["Department of Chemical Engineering, University of Utah, Salt Lake City, Utah, USA", "Universite Libre de Bruxelles, Aero-Thermo-Mechanics Laboratory, Brussels, Belgium"]
__license__ = "MIT"
__version__ = "1.0.0"
__maintainer__ = ["Kamila Zdybal", "Elizabeth Armstrong"]
__email__ = ["kamilazdybal@gmail.com", "Elizabeth.Armstrong@chemeng.utah.edu", "James.Sutherland@chemeng.utah.edu"]
__status__ = "Production"

# Module: `preprocess`
from .preprocess import center_scale
from .preprocess import invert_center_scale
from .preprocess import log_transform
from .preprocess import remove_constant_vars
from .preprocess import order_variables
from .preprocess import PreProcessing
from .preprocess import outlier_detection
from .preprocess import KernelDensity
from .preprocess import DataSampler
from .preprocess import ConditionalStatistics
from .preprocess import variable_bins
from .preprocess import predefined_variable_bins
from .preprocess import mixture_fraction_bins
from .preprocess import zero_neighborhood_bins
from .preprocess import degrade_clusters
from .preprocess import flip_clusters
from .preprocess import get_centroids
from .preprocess import get_partition
from .preprocess import get_populations
from .preprocess import get_average_centroid_distance
from .preprocess import plot_2d_clustering
from .preprocess import plot_3d_clustering
from .preprocess import plot_2d_train_test_samples
from .preprocess import plot_conditional_statistics

# Module: `reduction`
from .reduction import PCA
from .reduction import LPCA
from .reduction import SubsetPCA
from .reduction import pca_on_sampled_data_set
from .reduction import analyze_centers_change
from .reduction import analyze_eigenvector_weights_change
from .reduction import analyze_eigenvalue_distribution
from .reduction import equilibrate_cluster_populations
from .reduction import plot_2d_manifold
from .reduction import plot_3d_manifold
from .reduction import plot_2d_manifold_sequence
from .reduction import plot_parity
from .reduction import plot_mode
from .reduction import plot_eigenvectors
from .reduction import plot_eigenvectors_comparison
from .reduction import plot_eigenvalue_distribution
from .reduction import plot_eigenvalue_distribution_comparison
from .reduction import plot_cumulative_variance
from .reduction import plot_heatmap
from .reduction import plot_heatmap_sequence

# Module: `analysis`
from .kernel_regression import KReg
from .analysis import compute_normalized_variance
from .analysis import normalized_variance_derivative
from .analysis import find_local_maxima
from .analysis import random_sampling_normalized_variance
from .analysis import average_knn_distance
from .analysis import cost_function_normalized_variance_derivative
from .analysis import manifold_informed_feature_selection
from .analysis import manifold_informed_backward_elimination
from .analysis import RegressionAssessment
from .analysis import coefficient_of_determination
from .analysis import stratified_coefficient_of_determination
from .analysis import stratified_mean_absolute_error
from .analysis import stratified_mean_squared_error
from .analysis import stratified_root_mean_squared_error
from .analysis import stratified_normalized_root_mean_squared_error
from .analysis import mean_absolute_error
from .analysis import mean_squared_error
from .analysis import root_mean_squared_error
from .analysis import normalized_root_mean_squared_error
from .analysis import turning_points
from .analysis import good_estimate
from .analysis import good_direction_estimate
from .analysis import generate_tex_table
from .analysis import plot_2d_regression
from .analysis import plot_2d_regression_streamplot
from .analysis import plot_3d_regression
from .analysis import plot_normalized_variance
from .analysis import plot_normalized_variance_comparison
from .analysis import plot_normalized_variance_derivative
from .analysis import plot_normalized_variance_derivative_comparison
from .analysis import plot_stratified_metric
