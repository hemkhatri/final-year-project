# shop/tasks.py
from celery import shared_task
from django.core.cache import cache
from .recommender import HybridRecommender

@shared_task
def update_product_recommendations_cache(product_slug=None, user_id=None):
    if not product_slug:
        return
    
    recommender = HybridRecommender(alpha=0.5)
    recommendations = recommender.get_hybrid_recommendations(
        user_id=user_id, 
        product_slug=product_slug, 
        top_n=4
    )
    
    # Extract IDs to store in Redis
    rec_ids = [p.id for p in recommendations]
    
    # Save using product_slug key for 1 hour (3600s)
    cache_key = f"rec_product_{product_slug}"
    cache.set(cache_key, rec_ids, 3600)