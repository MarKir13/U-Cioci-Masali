{if $products}
<section class="ciocia-home-section ciocia-home-new" aria-labelledby="ciocia-home-new-title">
  <header class="ciocia-home-section__header">
    <div>
      <p class="ciocia-home-section__eyebrow">Właśnie dotarły</p>
      <h2 id="ciocia-home-new-title" class="ciocia-home-section__title">Nowości</h2>
    </div>
    <a class="ciocia-home-section__link" href="{$ciocia_all_url}">Zobacz wszystkie</a>
  </header>
  {include file='catalog/_partials/productlist.tpl' products=$products}
</section>
{/if}
