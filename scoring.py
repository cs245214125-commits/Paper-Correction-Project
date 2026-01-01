from sklearn.metrics.pairwise import cosine_similarity

def similarity_score(e1, e2):
    return cosine_similarity([e1], [e2])[0][0]

def calculate_marks(similarity, max_marks):
    return round(similarity * max_marks, 2)
