<section class="ciocia-home-section ciocia-home-guides" aria-labelledby="ciocia-home-guides-title">
  <header class="ciocia-home-section__header">
    <div>
      <p class="ciocia-home-section__eyebrow">Pomoc przed zakupem</p>
      <h2 id="ciocia-home-guides-title" class="ciocia-home-section__title">Zacznij od sprawdzonych wyborów</h2>
    </div>
  </header>
  <div class="ciocia-home-guides__grid">
    {foreach from=$ciocia_guides item=item}
      <article class="ciocia-home-guide">
        <i class="material-icons ciocia-home-guide__icon" aria-hidden="true">&#x{$item.icon};</i>
        <h3 class="ciocia-home-guide__title">{$item.title}</h3>
        <p>{$item.text}</p>
        <a href="{$item.url}">{$item.link}</a>
      </article>
    {/foreach}
  </div>
</section>
