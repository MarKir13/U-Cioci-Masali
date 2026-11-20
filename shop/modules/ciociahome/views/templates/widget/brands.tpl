<section class="ciocia-home-section ciocia-home-brands" aria-labelledby="ciocia-home-brands-title">
  <header class="ciocia-home-section__header">
    <div>
      <p class="ciocia-home-section__eyebrow">Sprawdzone źródła</p>
      <h2 id="ciocia-home-brands-title" class="ciocia-home-section__title">Popularne marki z Indii i świata Ajurwedy</h2>
    </div>
  </header>
  <nav class="ciocia-home-scroll ciocia-home-brands__track" aria-label="Popularne marki">
    {foreach from=$ciocia_brands item=item}
      <a class="ciocia-home-brand" href="{$item.url}">
        <strong>{$item.label}</strong>
        <span>{$item.meta}</span>
      </a>
    {/foreach}
  </nav>
</section>
