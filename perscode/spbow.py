from __future__ import division
import collections

import numpy as np

from sklearn.base import TransformerMixin
from sklearn.mixture import GaussianMixture

from .utils import to_landscape, _consolidate, _distanceclustercenter, _calcparameters, \
                   _sumithweights, weight_function

__all__ = ['sPBoW']

class sPBoW(TransformerMixin):
    """ Initialize a Persistence Bag of Words generator.


    Parameters
    -----------
    N : Length of codebook (length of vector)
    n_subsample : Number of points to be subsampled when calculating GMMs
    normalize : if set to True normalizes each vectorized persistence diagram with respect
                to the euclidean norm
    means_ : list or numpy array of 2d vectors representing the means of gaussian models
    weights_ : list or numpy array of values representing the weights of gaussian models
    covariances_ : list or numpy array of matrices representing the covariance matrices of gaussian
                   models



    Usage
    -----------
    >>> import perscode
    >>> # define length of codebook
    >>> length_codebook = 10
    >>> # number of points to be subsampled to calculate the gaussian mixtures
    >>> n_subsample = 10
    >>> spbow = perscode.sPBoW(N = length_codebook, n_subsample = 10)
    >>> spbow_diagrams = spbow.transform(diagrams) # diagrams is a list of persistence diagrams
    """
    def __init__(
        self,
        N = 10,
        n_subsample = 100,
        normalize = False,
        means_ = None,
        weights_ = None,
        covariances_ = None,
        ):
        # size of codebook
        self.N = N
        # number of points to be subsampled from the consolidated persistence diagram
        self.n_subsample = n_subsample
        # whether normalize or not the output
        self.normalize = normalize
        # means, weights and covariances from the GMM
        self.means_ = means_
        self.weights_ = weights_
        self.covariances_ = covariances_

    def transform(self, diagrams):
        """
        Convert diagram or list of diagrams to their respective vectors.


        Parameters
        -----------
        diagrams : list of or singleton diagram, list of pairs. [(birth, death)]
            Persistence diagrams to be converted to persistence images. It is assumed they are
            in (birth, death) format. Can input a list of diagrams or a single diagram.

        """

        # if diagram is empty, return zero vector
        if len(diagrams) == 0:
            return np.zeros(self.N)

         # if first entry of first entry is not iterable, then diagrams is singular and we need
         # to make it a list of diagrams
        try:
            singular = not isinstance(diagrams[0][0], collections.Iterable)
        except IndexError:
            singular = False

        if singular:
            diagrams = [diagrams]

        dgs = [np.copy(diagram).astype(np.float64) for diagram in diagrams]
        landscapes = [to_landscape(dg) for dg in dgs]

        # calculate gaussian mixture models
        weighting = self._getclustercenters(landscapes)

        # calculate inverse and determinant for each covariance matrix
        _calcparameters(self)

        spbows = [self._transform(dgm) for counter, dgm in enumerate(landscapes)]

        # Make sure we return one item.
        if singular:
            spbows = spbows[0]

        return spbows

    def _transform(self, landscape):
        """
        Calculate the stable persistence bag of words vector for the specified landscape
        """
        # number of gaussians calculated
        number_gaussians = self.N
        # define vector to be returned
        spbow_landscape = []
        for which_gaussian in range(number_gaussians):
            spbow_landscape.append(_sumithweights(self, landscape, which_gaussian))

        spbow_landscape = np.array(spbow_landscape)

        if self.normalize:
            return spbow_landscape/np.linalg.norm(spbow_landscape)
        else:
            return spbow_landscape

    def _getclustercenters(self, landscapes):
        """
        Cluster the consolidated diagram and return the cluster centers
        """
        # consolidate the landscapes
        consolidated_landscapes = _consolidate(self, landscapes)
        # get the 5th and 95th percentiles w.r.t. persistence points
        self.a, self.b = np.percentile(consolidated_landscapes[:,1], [5,95])
        # calculate the weight for every point with respect to the persistence.
        # if n_subsample is not an integer, e.g., None, all points should be sampled
        if not isinstance(self.n_subsample, int):
            weighting = [[1] * landscape.shape[0] for landscape in landscapes]
        else:
            weighting = [[weight_function(self, x[1]) for x in landscape] for landscape
                          in landscapes]
        if not (isinstance(self.means_, (np.ndarray, list))   and
                isinstance(self.weights_, (np.ndarray, list)) and
                isinstance(self.covariances_, (np.ndarray, list))):
            # consolidate weighting
            consolidated_weighting = np.concatenate(weighting)
            # normalize consolidated weighting
            consolidated_weighting = consolidated_weighting/np.sum(consolidated_weighting)
            # subsample the points respecting the weighting
            if not isinstance(self.n_subsample, int):
                subsampled_points = range(consolidated_weighting.shape[0])
            else:
                subsampled_points = np.random.choice(consolidated_landscapes.shape[0],
                       size=self.n_subsample, replace=False, p=consolidated_weighting)
            # get gaussians given the dataset
            gaussianmixture = GaussianMixture(n_components = self.N)
            gaussianmixture.fit(consolidated_landscapes[subsampled_points])
            # add the important values to class
            self.means_ = gaussianmixture.means_
            self.weights_ = gaussianmixture.weights_
            self.covariances_ = gaussianmixture.covariances_
        return weighting
