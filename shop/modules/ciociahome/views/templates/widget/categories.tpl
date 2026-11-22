<section class="ciocia-home-section ciocia-home-categories" aria-labelledby="ciocia-home-categories-title">
  <header class="ciocia-home-section__header">
    <div>
      <p class="ciocia-home-section__eyebrow">Ponad 1200 produktów</p>
      <h2 id="ciocia-home-categories-title" class="ciocia-home-section__title">Znajdź swój świat Magicznych Indii</h2>
    </div>
  </header>
  <nav class="ciocia-home-scroll ciocia-home-categories__track" aria-label="Najważniejsze kategorie">
    {foreach from=$ciocia_categories item=item}
      <a class="ciocia-home-category" href="{$item.url}">
        <i class="material-icons ciocia-home-category__icon" aria-hidden="true">{if !empty($item.svg)}<svg viewBox="0 0 24 24" width="1em" height="1em" fill="currentColor" focusable="false"><path d="{$item.svg}"/></svg>{else}&#x{$item.icon};{/if}</i>
        <span class="ciocia-home-category__title">{$item.label}</span>
        <span class="ciocia-home-category__meta">{$item.meta}</span>
      </a>
    {/foreach}
  </nav>
</section>
