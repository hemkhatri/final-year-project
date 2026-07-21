# shop/recommender.py
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from scipy.sparse.linalg import svds
from django.db.models import Case, When
from shop.models import Product, OrderItem

class HybridRecommender:
    def __init__(self, alpha=0.5):
        self.alpha = alpha

    def get_content_recommendations(self, target_product, top_n=10):
        # ... (Keep existing TF-IDF logic, it works well!) ...
        products = Product.objects.filter(available=True).prefetch_related('tags', 'category')
        
        if not products.exists():
            return Product.objects.none()

        product_list = list(products)
        product_ids = [p.id for p in product_list]

        if target_product.id not in product_ids:
            return Product.objects.none()

        corpus = []
        for p in product_list:
            tag_keywords = " ".join([t.keyword for t in p.tags.all()])
            cat_name = p.category.name if p.category else ""
            text_feature = f"{p.name} {cat_name} {p.relevant_tags or ''} {tag_keywords}".strip()
            corpus.append(text_feature)

        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(corpus)

        target_idx = product_ids.index(target_product.id)
        cosine_sim = cosine_similarity(tfidf_matrix[target_idx], tfidf_matrix).flatten()

        sim_scores = [(product_ids[i], score) for i, score in enumerate(cosine_sim) if product_ids[i] != target_product.id]
        sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)[:top_n]

        top_ids = [item[0] for item in sim_scores]
        return self._get_products_in_order(top_ids)

    def get_collaborative_recommendations(self, user_id, top_n=10):
        # ... (Keep existing SVD logic) ...
        items = OrderItem.objects.filter(
            order__buyer__isnull=False, 
            product__isnull=False
        ).values('order__buyer_id', 'product_id', 'quantity')

        if not items.exists():
            return Product.objects.none()

        df = pd.DataFrame(list(items))
        pivot_table = df.pivot_table(index='order__buyer_id', columns='product_id', values='quantity', aggfunc='sum').fillna(0)

        if user_id not in pivot_table.index:
            return Product.objects.none()

        matrix = pivot_table.to_numpy()
        user_means = np.mean(matrix, axis=1)
        matrix_demeaned = matrix - user_means.reshape(-1, 1)

        k = min(matrix.shape) - 1
        if k < 1:
            return Product.objects.none()

        U, sigma, Vt = svds(matrix_demeaned, k=k)
        sigma = np.diag(sigma)
        predicted_ratings = np.dot(np.dot(U, sigma), Vt) + user_means.reshape(-1, 1)

        preds_df = pd.DataFrame(predicted_ratings, columns=pivot_table.columns, index=pivot_table.index)
        user_preds = preds_df.loc[user_id].sort_values(ascending=False)

        already_purchased = df[df['order__buyer_id'] == user_id]['product_id'].tolist()
        rec_ids = [p_id for p_id in user_preds.index if p_id not in already_purchased][:top_n]

        return self._get_products_in_order(rec_ids)

    # CHANGED: Use product_slug instead of product_id
    def get_hybrid_recommendations(self, user_id=None, product_slug=None, top_n=4):
        """Blended Hybrid approach with Cold-Start fallback using Product Slug."""
        rec_ids_scores = {}

        # Content contribution (fetching via slug)
        if product_slug:
            try:
                target_p = Product.objects.get(slug=product_slug)
                content_recs = self.get_content_recommendations(target_p, top_n=top_n * 2)
                for idx, p in enumerate(content_recs):
                    rec_ids_scores[p.id] = rec_ids_scores.get(p.id, 0) + ((1 - self.alpha) * (1 / (idx + 1)))
            except Product.DoesNotExist:
                pass

        # Collaborative contribution
        if user_id:
            collab_recs = self.get_collaborative_recommendations(user_id, top_n=top_n * 2)
            for idx, p in enumerate(collab_recs):
                rec_ids_scores[p.id] = rec_ids_scores.get(p.id, 0) + (self.alpha * (1 / (idx + 1)))

        # Cold-Start Fallback
        if not rec_ids_scores:
            fallback = Product.objects.filter(available=True).order_by('-average_rating', '-total_bought')[:top_n]
            return fallback

        sorted_ids = sorted(rec_ids_scores, key=rec_ids_scores.get, reverse=True)[:top_n]
        return self._get_products_in_order(sorted_ids)

    def _get_products_in_order(self, id_list):
        if not id_list:
            return Product.objects.none()
        preserved_order = Case(*[When(id=pk, then=pos) for pos, pk in enumerate(id_list)])
        return Product.objects.filter(id__in=id_list, available=True).order_by(preserved_order)


