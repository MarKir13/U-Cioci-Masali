<section class="ciocia-home-section ciocia-home-needs" aria-labelledby="ciocia-home-needs-title">
  <header class="ciocia-home-section__header">
    <div>
      <p class="ciocia-home-section__eyebrow">Zakupy bez błądzenia</p>
      <h2 id="ciocia-home-needs-title" class="ciocia-home-section__title">Czego dziś potrzebujesz?</h2>
    </div>
  </header>
  <nav class="ciocia-home-scroll ciocia-home-needs__track" aria-label="Zakupy według potrzeby">
    {foreach from=$ciocia_needs item=item}
      <a class="ciocia-home-need" href="{$item.url}">
        <span class="ciocia-home-need__icon" aria-hidden="true">{$item.icon}</span>
        <span>{$item.label}</span>
      </a>
    {/foreach}
  </nav>
</section>
