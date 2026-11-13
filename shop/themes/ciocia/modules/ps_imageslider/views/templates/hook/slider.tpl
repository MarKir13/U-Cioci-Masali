{*
 * Home page banner (issue #63), as the hero section on magiczne-indie.pl: image slider on the left,
 * a short text and two buttons on the right. Replaces Classic's slider template, so it shows where
 * ps_imageslider is hooked: at the top of the home page (hook displayHome) only.
 *
 * Do not edit the texts here. Slides come from the module (ps_imageslider), texts and button links
 * from the CIOCIA_BANNER_* settings; shop-content.php writes both from 'home_banner' in
 * shop/config/shop-settings.php.
 *
 * The slider uses Bootstrap 4's carousel from Classic. As on the source it does not slide by itself
 * (data-interval="false"): it changes only when the customer clicks an arrow or swipes.
 *}
<section class="ciocia-hero" aria-labelledby="ciocia-hero-title">
  {if $homeslider.slides}
    <div class="ciocia-hero__media">
      <div id="carousel" class="carousel slide" data-interval="false" data-wrap="true" data-touch="true">
        <ul class="carousel-inner" aria-label="Zdjęcia sklepu">
          {foreach from=$homeslider.slides item=slide name='homeslider'}
            <li class="carousel-item{if $smarty.foreach.homeslider.first} active{/if}">
              <img src="{$slide.image_url|escape:'htmlall':'UTF-8'}" alt="{$slide.legend|escape:'htmlall':'UTF-8'}"
                   {if isset($slide.sizes[0])}width="{$slide.sizes[0]|intval}" height="{$slide.sizes[1]|intval}"{/if}
                   {if $smarty.foreach.homeslider.first}fetchpriority="high"{else}loading="lazy"{/if}>
            </li>
          {/foreach}
        </ul>
        {if $homeslider.slides|count > 1}
          <button class="ciocia-hero__arrow ciocia-hero__arrow--prev" type="button" data-target="#carousel" data-slide="prev" aria-label="Poprzednie zdjęcie">
            <i class="material-icons" aria-hidden="true">&#xE5CB;</i>
          </button>
          <button class="ciocia-hero__arrow ciocia-hero__arrow--next" type="button" data-target="#carousel" data-slide="next" aria-label="Następne zdjęcie">
            <i class="material-icons" aria-hidden="true">&#xE5CC;</i>
          </button>
        {/if}
      </div>
    </div>
  {/if}
  <div class="ciocia-hero__content">
    <p class="ciocia-hero__eyebrow">{Configuration::get('CIOCIA_BANNER_EYEBROW')|escape:'htmlall':'UTF-8'}</p>
    <h1 id="ciocia-hero-title" class="ciocia-hero__title">{Configuration::get('CIOCIA_BANNER_TITLE')|escape:'htmlall':'UTF-8'}</h1>
    <p class="ciocia-hero__lead">{Configuration::get('CIOCIA_BANNER_LEAD')|escape:'htmlall':'UTF-8'}</p>
    <div class="ciocia-hero__actions">
      <a class="btn btn-primary" href="{Configuration::get('CIOCIA_BANNER_PRIMARY_URL')|escape:'htmlall':'UTF-8'}">
        {Configuration::get('CIOCIA_BANNER_PRIMARY_LABEL')|escape:'htmlall':'UTF-8'}
      </a>
      <a class="btn btn-outline-primary" href="{Configuration::get('CIOCIA_BANNER_SECONDARY_URL')|escape:'htmlall':'UTF-8'}">
        {Configuration::get('CIOCIA_BANNER_SECONDARY_LABEL')|escape:'htmlall':'UTF-8'}
      </a>
    </div>
  </div>
</section>
