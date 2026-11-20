{if $products}
<section class="ciocia-home-section ciocia-home-featured" aria-labelledby="ciocia-home-featured-title">
  <header class="ciocia-home-section__header">
    <div>
      <p class="ciocia-home-section__eyebrow">Dobry wybór na początek</p>
      <h2 id="ciocia-home-featured-title" class="ciocia-home-section__title">Polecane produkty</h2>
    </div>
    <a class="ciocia-home-section__link" href="{$ciocia_all_url}">Zobacz wszystkie</a>
  </header>
  {include file='catalog/_partials/productlist.tpl' products=$products}
</section>
{/if}
