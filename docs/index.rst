.. image:: ../PCAfold-logo.png
  :width: 500

*Low-dimensional PCA-derived manifolds and everything in between!*

--------------------------------------------------------------------------------

**PCAfold** is an open-source Python library for generating, analyzing and improving
empirical low-dimensional manifolds obtained via Principal Component Analysis
(PCA). It incorporates a variety of data preprocessing tools (including data
clustering and sampling), uses PCA as a dimensionality reduction technique
and utilizes a novel approach to assess the quality of the obtained
low-dimensional manifolds.

A general overview for using **PCAfold** modules is presented in the diagram
below:

.. image:: images/PCAfold-diagram.png
  :width: 700
  :align: center

Each module's functionalities can also be used as a standalone tool for
performing a specific task and can easily combine with techniques outside of
this software, such as K-Means algorithm or Artificial Neural Networks.

Reach out to the `Getting started <https://pcafold.readthedocs.io/en/latest/user/getting-started.html#workflows>`_
section for possible workflows that can be achieved with **PCAfold**.

--------------------------------------------------------------------------------

Citing PCAfold
==============

**PCAfold** is published in `SoftwareX journal <https://authors.elsevier.com/sd/article/S2352711020303435>`_.
If you use **PCAfold** in a scientific publication, you can cite the software as:

.. code-block:: text

  @article{zdybal2020pcafold,
  title = "PCAfold: Python software to generate, analyze and improve PCA-derived low-dimensional manifolds",
  journal = "SoftwareX",
  volume = "12",
  pages = "100630",
  year = "2020",
  issn = "2352-7110",
  doi = "https://doi.org/10.1016/j.softx.2020.100630",
  url = "http://www.sciencedirect.com/science/article/pii/S2352711020303435",
  author = "Kamila Zdybał and Elizabeth Armstrong and Alessandro Parente and James C. Sutherland"
  }

--------------------------------------------------------------------------------

.. toctree::
   :maxdepth: 5
   :caption: User Guide

   user/getting-started
   user/data-preprocessing
   user/data-reduction
   user/data-analysis

.. toctree::
   :maxdepth: 2
   :caption: Tutorials & Demos

   tutorials/demo-data-manipulation
   tutorials/demo-clustering
   tutorials/demo-sampling
   tutorials/demo-plotting-pca
   tutorials/demo-global-vs-local-pca
   tutorials/demo-pca-on-sampled-data-sets
   tutorials/demo-handling-source-terms
   tutorials/demo-manifold-assessment