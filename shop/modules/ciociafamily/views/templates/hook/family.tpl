{* Product family rows (issue #114), styled in the child theme: .ciocia-family in themes/ciocia/assets/css/custom.css *}
<nav class="ciocia-family" aria-label="Warianty produktu">
  {foreach from=$ciocia_family item=row}
    <div class="ciocia-family__row">
      {if $row.title}
        <p class="ciocia-family__title">{$row.title|escape:'html':'UTF-8'}</p>
      {/if}
      <div class="ciocia-family__options ciocia-family__options--{$row.kind|escape:'html':'UTF-8'}">
        {foreach from=$row.tiles item=tile}
          {* The current product is not a link, as on the source *}
          {if $tile.current}
            <span class="ciocia-family__tile is-current" aria-current="page" title="{$tile.name|escape:'html':'UTF-8'}">
          {else}
            <a class="ciocia-family__tile" href="{$tile.url|escape:'html':'UTF-8'}" title="{$tile.name|escape:'html':'UTF-8'}">
          {/if}
            {if $row.kind == 'image'}
              {if $tile.image}
                {* The label next to it names the tile, so the photo is decorative *}
                <img src="{$tile.image|escape:'html':'UTF-8'}" alt="" width="250" height="250" loading="lazy">
              {else}
                <span class="ciocia-family__no-image"></span>
              {/if}
            {/if}
            <span class="ciocia-family__label">{$tile.label|escape:'html':'UTF-8'}</span>
          {if $tile.current}</span>{else}</a>{/if}
        {/foreach}
      </div>
    </div>
  {/foreach}
</nav>
