{**
 * Adapted from Classic, copyright since 2007 PrestaShop SA and Contributors.
 * Licensed under the Academic Free License 3.0 (AFL-3.0).
 * https://opensource.org/licenses/AFL-3.0
 *}
{*
 * 404 page as on the source: a large "404", one sentence, a link to the contact page and a button
 * back to the home page, in a narrow centred card (CSS: #pagenotfound in custom.css).
 *}
{extends file='page.tpl'}

{block name="breadcrumb"}{/block}

{block name='page_header_container'}
  <div class="page-header ciocia-404-code" aria-hidden="true">404</div>
{/block}

{block name='page_content_container'}
  <section id="content" class="page-content page-not-found">
    <h1 class="h2">Szukana strona nie została odnaleziona.</h1>
    <p>Jeśli to się powtarza, <a href="{$urls.pages.contact}">skontaktuj się z nami</a>.</p>
    <a class="btn btn-primary ciocia-404-home" href="{$urls.pages.index}">
      <i class="material-icons" aria-hidden="true">arrow_back</i>
      Wróć do strony głównej
    </a>
    {block name='hook_not_found'}
      {hook h='displayNotFound'}
    {/block}
  </section>
{/block}
