# Return data frame of a draw of relative percent of occurrence from a beta distribution
# fit to observed occurrence counts
#   df: data frame where rows = ASVs and columns = samples
def ranRelPct(df, asLogOdds = True):
    import cupy as cp
    import numpy as np
    
    result = df.copy()
    for i in range(df.shape[1]):
        col = df.iloc[:,i]
        a = col + 1
        b = col.sum() - col + 1
        beta_dist = cp.random.beta(a,b)
        beta_dist /= beta_dist.sum()
        result.iloc[:,i] = beta_dist
    # convert to log-odds if requested
    if asLogOdds:
        # need to use numpy for this transformation not cupy
        result = np.log(result / (1 - result))
    return result.transpose()


# Does PCA
#   df: data frame where rows = samples and columns = ASVs
#   num_pcs: number of components to return. if None, return maximum number
# Returns a dictionary containing :
#   scores: array of PCA scores
#   loadings: array of PCA loadings
def doPCA(df, num_pcs = None):
    from cuml.decomposition import PCA
    import numpy as np
    
    max_pcs = min(df.shape[0] - 1, df.shape[1] - 1)
    if num_pcs is None:
        num_pcs = max_pcs
    elif num_pcs > max_pcs:
        num_pcs = max_pcs
    pca = PCA(n_components = num_pcs)
    pca_fit = pca.fit(df)
    pca_results = {
        "scores": pca_fit.transform(df),
        "loadings": np.transpose(pca_fit.components_)
    }
    return pca_results


# If the sign of the first element in a column in matrices after the first is different than the first,
# multiply all values in that column by -1
def harmonizeColumnSigns(mat_list):
    for i in range(1, len(mat_list)):
        for col in range(mat_list[i].shape[1]):
            if cp.sign(mat_list[i][0, col]) != cp.sign(mat_list[0][0, col]):
                mat_list[i][:, col] *= -1
    return mat_list


# Sorts PCA loadings from a list 
def sortLoadings(loading_list, pc, asvs, asRanks = False):
    # Harmonize signs across replicates
    harm_loadings = harmonizeColumnSigns(loading_list)
    # Create 3 dimensional array and select component 'pc'
    loadings = cp.stack(harm_loadings, axis = 2)[:, pc, :]
    # Convert to ranks if 'asRanks == True'
    if asRanks:
        loadings = cp.array([rankdata(loadings[:, i]) for i in range(loadings.shape[1])]).transpose()
    # Get sorted order based on median for each ASV 
    row_sort = cp.apply_along_axis(np.median, 1, loadings).ravel().argsort()[::-1]
    # Sort based on median, add ASV names (also sorted) and return data frame
    df = cudf.DataFrame(loadings[row_sort, :])
    df.index = asvs[row_sort]
    return df


# Does hierarchical clustering on data frame where rows are samples and columns are ASVs
# Returns array of cluster labels for rows
def doClustering(df, num_clusts, num_pcs = None):
    from cuml import AgglomerativeClustering as aggclust
    
    agg_clust = aggclust(n_clusters = num_clusts, affinity = "euclidean", 
                         linkage = "single", output_type="cudf")
    labels = agg_clust.fit_predict(df)
    return labels.astype(int)